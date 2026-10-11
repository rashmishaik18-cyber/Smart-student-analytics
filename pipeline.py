"""
pipeline.py  -  integrate -> clean -> score -> flag risk -> segment -> export

Reads  : data/raw/*.csv (10 disconnected sources)
Writes : data/student_master.csv      one row per student (unified view)
         data/data_quality_report.json
         dashboard/data.js            data bundle the dashboard loads
"""
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW, OUT, DASH = ROOT / "data" / "raw", ROOT / "data", ROOT / "dashboard"

# ----------------------------------------------------------------------------
# 1. STUDENT SUCCESS SCORE DEFINITION  (key, label, pillar, weight)  -> sums to 1
# ----------------------------------------------------------------------------
INDICATORS = [
    ("cgpa", "CGPA", "Academic", .16),
    ("internal", "Internal assessment marks", "Academic", .09),
    ("backlog", "Backlog-free record", "Academic", .07),
    ("subject", "Average subject marks", "Academic", .03),
    ("attendance", "Overall attendance", "Attendance", .10),
    ("att_low", "Lowest-subject attendance", "Attendance", .05),
    ("logins", "LMS login frequency", "LMS", .04),
    ("assign", "Assignment completion", "LMS", .06),
    ("engage", "Co-curricular engagement", "Engagement", .10),
    ("aptitude", "Aptitude score", "Placement", .06),
    ("coding", "Coding score", "Placement", .08),
    ("mock", "Mock interview score", "Placement", .06),
    ("tech", "Technical skills", "Skills", .03),
    ("soft", "Soft skills", "Skills", .02),
    ("satisfaction", "Student satisfaction", "Feedback", .02),
    ("faculty", "Faculty feedback", "Feedback", .03),
]
KEYS = [i[0] for i in INDICATORS]
W = np.array([i[3] for i in INDICATORS])
PILLARS = ["Academic", "Attendance", "LMS", "Engagement", "Placement", "Skills", "Feedback"]
assert abs(W.sum() - 1) < 1e-9

BANDS = [(75, "Excellent"), (60, "Good"), (45, "Watch"), (-1, "Critical")]
DEPT_MAP = {"cse": "CSE", "computerscience": "CSE", "compsci": "CSE", "it": "IT", "informationtechnology": "IT",
            "infotech": "IT", "ece": "ECE", "electronics": "ECE", "mech": "MECH", "mechanical": "MECH",
            "civil": "CIVIL", "civilengg": "CIVIL"}
MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------------------
# 2. CLEANING HELPERS
# ----------------------------------------------------------------------------
def norm_id(v):
    d = re.sub(r"\D", "", str(v))
    return f"S{int(d):04d}" if d else None


def to_year(v):
    m = re.search(r"\d", str(v))
    return int(m.group()) if m else None


def clean_source(name, df, key=("student_id",), ranges=None):
    """Standardise IDs, drop duplicates, repair or null out-of-range values."""
    rep = {"source": name, "rows_raw": int(len(df))}
    df = df.copy()
    raw = df["student_id"].astype(str)
    df["student_id"] = df["student_id"].map(norm_id)
    rep["ids_standardised"] = int((raw != df["student_id"]).sum())
    n = len(df)
    df = df.drop_duplicates(subset=list(key), keep="first")
    rep["duplicates_removed"] = n - len(df)
    fixed = 0
    for col, (lo, hi) in (ranges or {}).items():
        s = pd.to_numeric(df[col], errors="coerce")
        if col == "cgpa":                               # % scale entered by mistake
            m = (s > hi) & (s <= 100)
            s = s.where(~m, s / 10)
            fixed += int(m.sum())
        over = (s > hi) & (s <= hi * 1.15)              # small overshoot -> cap
        s = s.where(~over, hi)
        fixed += int(over.sum())
        bad = (s < lo) | (s > hi)                       # sentinel / impossible -> missing
        fixed += int(bad.sum())
        df[col] = s.where(~bad, np.nan)
    rep["outliers_fixed"] = fixed
    return df, rep


def r1(x, d=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


# ----------------------------------------------------------------------------
# 3. LOAD + INTEGRATE
# ----------------------------------------------------------------------------
def build_master():
    reports = []
    acad, rep = clean_source("academic.csv", pd.read_csv(RAW / "academic.csv"),
                             ranges={"cgpa": (0, 10), "internal_marks_avg": (0, 100), "backlogs": (0, 15)})
    acad["department"] = acad["department"].map(lambda x: DEPT_MAP.get(re.sub(r"[^a-z]", "", str(x).lower())))
    acad["year"] = acad["year"].map(to_year)
    acad = acad.dropna(subset=["student_id", "department", "year"]).copy()
    acad["year"] = acad["year"].astype(int)
    spine = set(acad["student_id"])
    rep["orphans_dropped"] = 0
    rep["students_missing"] = 0
    reports.append((rep, ["cgpa", "internal_marks_avg", "backlogs"]))

    sources = {
        "attendance.csv": ({"overall_attendance_pct": (0, 100), "lowest_subject_pct": (0, 100)}, ("student_id",)),
        "lms.csv": ({"logins_per_week": (0, 50), "assignment_completion_pct": (0, 100),
                     "avg_session_minutes": (0, 600)}, ("student_id",)),
        "engagement.csv": ({"events_attended": (0, 60), "clubs": (0, 15), "hackathons": (0, 30),
                            "certifications": (0, 30)}, ("student_id",)),
        "placement.csv": ({"aptitude_score": (0, 100), "coding_score": (0, 100), "mock_interview_score": (0, 100),
                           "mock_interviews_attended": (0, 50)}, ("student_id",)),
        "skills.csv": ({"technical_skill": (0, 100), "soft_skill": (0, 100)}, ("student_id",)),
        "feedback.csv": ({"satisfaction": (1, 5), "faculty_rating": (1, 5)}, ("student_id",)),
    }
    master = acad.drop(columns=[]).copy()
    for fname, (ranges, key) in sources.items():
        df, rep = clean_source(fname, pd.read_csv(RAW / fname), key, ranges)
        n = len(df)
        df = df[df["student_id"].isin(spine)]
        rep["orphans_dropped"] = n - len(df)
        rep["students_missing"] = len(spine - set(df["student_id"]))
        master = master.merge(df[["student_id"] + list(ranges)], on="student_id", how="left")
        reports.append((rep, list(ranges)))

    # long tables -> per-student structures
    sem, rep = clean_source("academic_semesters.csv", pd.read_csv(RAW / "academic_semesters.csv"),
                            ("student_id", "semester"), {"sgpa": (0, 10)})
    n = len(sem); sem = sem[sem["student_id"].isin(spine)]
    rep.update(orphans_dropped=n - len(sem), students_missing=len(spine - set(sem["student_id"])))
    reports.append((rep, ["sgpa"]))
    mon, rep = clean_source("attendance_monthly.csv", pd.read_csv(RAW / "attendance_monthly.csv"),
                            ("student_id", "month"), {"attendance_pct": (0, 100)})
    n = len(mon); mon = mon[mon["student_id"].isin(spine)]
    rep.update(orphans_dropped=n - len(mon), students_missing=len(spine - set(mon["student_id"])))
    reports.append((rep, ["attendance_pct"]))
    sub, rep = clean_source("subject_marks.csv", pd.read_csv(RAW / "subject_marks.csv"),
                            ("student_id", "subject"), {"marks": (0, 100)})
    n = len(sub); sub = sub[sub["student_id"].isin(spine)]
    rep.update(orphans_dropped=n - len(sub), students_missing=len(spine - set(sub["student_id"])))
    reports.append((rep, ["marks"]))
    master = master.merge(sub.groupby("student_id")["marks"].mean().rename("subject_avg").reset_index(),
                          on="student_id", how="left")

    # impute: department x year median -> department median -> campus median
    value_cols = [c for c in master.columns if c not in ("student_id", "name", "department", "year")]
    miss = master[value_cols].isna()
    for rep, cols in reports:
        cols_in = [c for c in cols if c in master.columns]
        rep["cells_imputed"] = int(miss[cols_in].sum().sum()) if cols_in else int(rep.get("rows_raw", 0) * 0)
    for c in value_cols:
        m = master.groupby(["department", "year"])[c].transform("median")
        m = m.fillna(master.groupby("department")[c].transform("median")).fillna(master[c].median())
        master[c] = master[c].fillna(m)
    master["imputed_fields"] = miss.sum(axis=1).values
    master["completeness"] = (1 - master["imputed_fields"] / len(value_cols)).round(3)
    dq = [r for r, _ in reports]
    for r in dq:
        r["rows_clean"] = r["rows_raw"] - r["duplicates_removed"] - r["orphans_dropped"]
    return master.reset_index(drop=True), sem, mon, sub, dq


# ----------------------------------------------------------------------------
# 4. SCORE
# ----------------------------------------------------------------------------
def indicators(m):
    X = pd.DataFrame(index=m.index)
    X["cgpa"] = m["cgpa"] * 10
    X["internal"] = m["internal_marks_avg"]
    X["backlog"] = (100 - 25 * m["backlogs"]).clip(0, 100)
    X["subject"] = m["subject_avg"]
    X["attendance"] = m["overall_attendance_pct"]
    X["att_low"] = m["lowest_subject_pct"]
    X["logins"] = (m["logins_per_week"] / 10 * 100).clip(0, 100)
    X["assign"] = m["assignment_completion_pct"]
    X["engage"] = 100 * (.30 * (m["events_attended"] / 8).clip(0, 1) + .20 * (m["clubs"] / 3).clip(0, 1)
                         + .25 * (m["hackathons"] / 3).clip(0, 1) + .25 * (m["certifications"] / 4).clip(0, 1))
    X["aptitude"] = m["aptitude_score"]
    X["coding"] = m["coding_score"]
    X["mock"] = m["mock_interview_score"]
    X["tech"] = m["technical_skill"]
    X["soft"] = m["soft_skill"]
    X["satisfaction"] = (m["satisfaction"] - 1) / 4 * 100
    X["faculty"] = (m["faculty_rating"] - 1) / 4 * 100
    return X[KEYS].clip(0, 100)


def band(s):
    return next(n for t, n in BANDS if s >= t)


# ----------------------------------------------------------------------------
# 5. RISK RULES  (transparent points system: every flag has stated reasons)
#    (condition, points, reason text, recommended action)
# ----------------------------------------------------------------------------
ACADEMIC_RULES = [
    (lambda r: r["cgpa"] < 6.0, 3, lambda r: f"CGPA {r['cgpa']:.2f} is below 6.0", "Assign a faculty mentor and weekly academic review"),
    (lambda r: 6.0 <= r["cgpa"] < 7.0, 1, lambda r: f"CGPA {r['cgpa']:.2f} is below 7.0", "Enrol in peer-tutoring group"),
    (lambda r: r["backlogs"] >= 3, 3, lambda r: f"{int(r['backlogs'])} active backlogs", "Remedial classes and a backlog-clearing plan"),
    (lambda r: 1 <= r["backlogs"] < 3, 1, lambda r: f"{int(r['backlogs'])} active backlog(s)", "Backlog-clearing plan before next exams"),
    (lambda r: r["att"] < 65, 3, lambda r: f"Attendance {r['att']:.1f}% is below 65%", "Call parents and set an attendance contract"),
    (lambda r: 65 <= r["att"] < 75, 2, lambda r: f"Attendance {r['att']:.1f}% is below the 75% eligibility line", "Mentor check-in on attendance this week"),
    (lambda r: r["internal"] < 50, 2, lambda r: f"Internal marks average {r['internal']:.0f}/100", "Targeted doubt-clearing sessions"),
    (lambda r: 50 <= r["internal"] < 60, 1, lambda r: f"Internal marks average {r['internal']:.0f}/100", "Doubt-clearing sessions"),
    (lambda r: r["trend"] <= -0.6, 2, lambda r: f"SGPA fell {abs(r['trend']):.1f} points vs recent semesters", "Early counselling to find what changed"),
    (lambda r: r["assign"] < 50, 1, lambda r: f"Only {r['assign']:.0f}% of LMS assignments completed", "Assignment tracking with weekly nudges"),
]
PLACEMENT_RULES = [
    (lambda r: r["plc"] < 50, 3, lambda r: f"Placement readiness {r['plc']:.0f}/100", "Structured placement-prep track"),
    (lambda r: 50 <= r["plc"] < 60, 1, lambda r: f"Placement readiness {r['plc']:.0f}/100", "Weekly aptitude and mock practice"),
    (lambda r: r["coding"] < 40, 2, lambda r: f"Coding score {r['coding']:.0f}/100", "Daily coding practice with a lab mentor"),
    (lambda r: r["aptitude"] < 50, 1, lambda r: f"Aptitude score {r['aptitude']:.0f}/100", "Aptitude training batch"),
    (lambda r: r["mock"] < 45, 1, lambda r: f"Mock interview score {r['mock']:.0f}/100", "Book 2 mock interviews with feedback"),
    (lambda r: r["cgpa"] < 6.0, 2, lambda r: "CGPA is below the common 6.0 placement cut-off", "Academic recovery plan to restore eligibility"),
    (lambda r: r["backlogs"] >= 1, 1, lambda r: "Active backlog can block company eligibility", "Clear backlogs before placement season"),
    (lambda r: r["engage"] < 25, 1, lambda r: "Little co-curricular activity to show recruiters", "Join a club, hackathon or certification"),
    (lambda r: r["tech"] < 45, 1, lambda r: f"Technical skill {r['tech']:.0f}/100", "Technical skill workshop"),
    (lambda r: r["soft"] < 45, 1, lambda r: f"Soft-skill score {r['soft']:.0f}/100", "Communication and interview skills workshop"),
]
ACAD_HIGH, ACAD_MED, PLC_HIGH, PLC_MED = 7, 3, 8, 4

SEGMENTS = {
    "Needs urgent support": ("Academic and placement risk are both high.", "Mentor assigned within a week; combined academic + placement recovery plan."),
    "Strong academics, low placement readiness": ("Good academic pillar but weak aptitude, coding or interview preparation.", "Placement bootcamp, mock interviews and industry exposure."),
    "Placement-ready, academics slipping": ("Prepared for placement but academic risk is rising.", "Protect eligibility: backlog clearing and academic coaching."),
    "Disengaged": ("Low attendance, LMS use and co-curricular activity together.", "Mentor outreach to re-engage; clubs and peer groups."),
    "Star performers": ("High score and low risk on both fronts.", "Stretch work: research, leadership and peer-mentor roles."),
    "Steady middle": ("No major flag; room to improve.", "Light-touch nudges and skill-building opportunities."),
}


def level(pts, hi, med):
    return "High" if pts >= hi else "Medium" if pts >= med else "Low"


def segment(r):
    if r["acad_risk"] == "High" and r["plc_risk"] == "High":
        return "Needs urgent support"
    if r["p_Academic"] >= 70 and r["p_Placement"] < 48:
        return "Strong academics, low placement readiness"
    if r["p_Placement"] >= 60 and r["acad_risk"] != "Low":
        return "Placement-ready, academics slipping"
    if r["engage"] < 35 and r["p_LMS"] < 62 and r["att"] < 78:
        return "Disengaged"
    if r["score"] >= 70 and r["acad_risk"] == "Low" and r["plc_risk"] == "Low":
        return "Star performers"
    return "Steady middle"


# ----------------------------------------------------------------------------
# 6. MAIN
# ----------------------------------------------------------------------------
def main():
    master, sem, mon, sub, dq = build_master()
    X = indicators(master)
    score = (X * W).sum(axis=1)
    pillar = {p: (X[[k for k, _, pp, _ in INDICATORS if pp == p]] *
                  np.array([w for _, _, pp, w in INDICATORS if pp == p])).sum(axis=1) /
                 sum(w for _, _, pp, w in INDICATORS if pp == p) for p in PILLARS}
    plc_ready = (.3 * X["aptitude"] + .4 * X["coding"] + .3 * X["mock"])
    delta = (X - X.mean()) * W                      # points vs campus average (explainability)

    sem = sem.sort_values(["student_id", "semester"])
    sg = sem.groupby("student_id")["sgpa"].apply(list).to_dict()
    mo = mon.assign(m=mon["month"].map({m: i for i, m in enumerate(MONTHS)})).sort_values(["student_id", "m"])
    mg = mo.groupby("student_id")["attendance_pct"].apply(list).to_dict()
    subj = {sid: dict(zip(g["subject"], g["marks"])) for sid, g in sub.groupby("student_id")}

    recs = []
    for i, row in master.iterrows():
        sid = row["student_id"]
        vals = sg.get(sid, [])
        trend = (vals[-1] - np.mean(vals[-3:-1])) if len(vals) >= 3 else 0.0
        forecast = None
        if len(vals) >= 3:
            sl, ic = np.polyfit(np.arange(len(vals)), vals, 1)
            forecast = float(np.clip(vals[-1] + .5 * sl, 0, 10))
        r = dict(cgpa=row["cgpa"], backlogs=row["backlogs"], att=row["overall_attendance_pct"],
                 internal=row["internal_marks_avg"], trend=trend, assign=row["assignment_completion_pct"],
                 plc=plc_ready[i], coding=X.at[i, "coding"], aptitude=X.at[i, "aptitude"], mock=X.at[i, "mock"],
                 engage=X.at[i, "engage"], tech=X.at[i, "tech"], soft=X.at[i, "soft"])
        a_hits = [(p, t(r), act) for c, p, t, act in ACADEMIC_RULES if c(r)]
        p_hits = [(p, t(r), act) for c, p, t, act in PLACEMENT_RULES if c(r)]
        a_pts, p_pts = sum(h[0] for h in a_hits), sum(h[0] for h in p_hits)
        a_lvl, p_lvl = level(a_pts, ACAD_HIGH, ACAD_MED), level(p_pts, PLC_HIGH, PLC_MED)
        seg = segment(dict(acad_risk=a_lvl, plc_risk=p_lvl, p_Academic=pillar["Academic"][i],
                           p_Placement=plc_ready[i], p_LMS=pillar["LMS"][i], engage=r["engage"],
                           att=r["att"], score=score[i]))
        overall = "High" if "High" in (a_lvl, p_lvl) else "Medium" if "Medium" in (a_lvl, p_lvl) else "Low"
        hits = sorted([("A", *h) for h in a_hits] + [("P", *h) for h in p_hits], key=lambda h: -h[1])
        actions = []
        for h in hits:
            if h[3] not in actions:
                actions.append(h[3])
        recs.append({
            "id": sid, "name": row["name"], "dept": row["department"], "year": int(row["year"]),
            "cgpa": r1(row["cgpa"], 2), "internal": r1(row["internal_marks_avg"]), "backlogs": int(row["backlogs"]),
            "att": r1(row["overall_attendance_pct"]), "att_low": r1(row["lowest_subject_pct"]),
            "assign": r1(row["assignment_completion_pct"]), "logins": r1(row["logins_per_week"]),
            "events": int(round(row["events_attended"])), "clubs": int(round(row["clubs"])),
            "hack": int(round(row["hackathons"])), "certs": int(round(row["certifications"])),
            "apt": r1(row["aptitude_score"]), "coding": r1(row["coding_score"]), "mock": r1(row["mock_interview_score"]),
            "tech": r1(row["technical_skill"]), "soft": r1(row["soft_skill"]),
            "sat": r1(row["satisfaction"]), "fac": r1(row["faculty_rating"]),
            "score": r1(score[i]), "band": band(score[i]),
            "pillars": {p: r1(pillar[p][i]) for p in PILLARS},
            "plc_ready": r1(plc_ready[i]),
            "acad_pts": int(a_pts), "plc_pts": int(p_pts), "acad_risk": a_lvl, "plc_risk": p_lvl, "risk": overall,
            "segment": seg, "reasons": [h[2] for h in hits[:5]], "actions": actions[:3],
            "drivers": [r1(delta.at[i, k]) for k in KEYS],
            "sgpa": [round(v, 2) for v in vals], "forecast": r1(forecast, 2),
            "att_monthly": [round(v, 1) for v in mg.get(sid, [])],
            "subjects": {k: round(v, 1) for k, v in subj.get(sid, {}).items()},
            "completeness": float(row["completeness"]),
            "priority": r1(a_pts + p_pts + (100 - score[i]) / 10),
        })

    df = pd.DataFrame(recs)
    insights = build_insights(df, master, X)
    sgpa_by_sem = [r1(np.mean([r["sgpa"][s] for r in recs if len(r["sgpa"]) > s]), 2) for s in range(7)]
    att_by_month = [r1(np.mean([r["att_monthly"][s] for r in recs if len(r["att_monthly"]) > s])) for s in range(6)]

    meta = {
        "generated": datetime.now().strftime("%d %b %Y"),
        "indicators": [{"key": k, "label": l, "pillar": p, "weight": w} for k, l, p, w in INDICATORS],
        "pillars": PILLARS, "months": MONTHS,
        "cohort_means": {k: r1(X[k].mean()) for k in KEYS},
        "bands": [{"min": t, "name": n} for t, n in BANDS],
        "thresholds": {"acad_high": ACAD_HIGH, "acad_med": ACAD_MED, "plc_high": PLC_HIGH, "plc_med": PLC_MED},
        "segments": {k: {"what": v[0], "action": v[1]} for k, v in SEGMENTS.items()},
        "rule_text": {
            "academic": ["CGPA below 6.0 (+3) or below 7.0 (+1)", "3+ backlogs (+3) or 1-2 backlogs (+1)",
                         "Attendance below 65% (+3) or below 75% (+2)", "Internal marks below 50 (+2) or below 60 (+1)",
                         "SGPA fell 0.6+ vs recent semesters (+2)", "Assignment completion below 50% (+1)"],
            "placement": ["Placement readiness below 50 (+3) or below 60 (+1)", "Coding score below 40 (+2)",
                          "Aptitude below 50 (+1)", "Mock interview below 45 (+1)", "CGPA below 6.0 cut-off (+2)",
                          "Active backlog (+1)", "Engagement index below 25 (+1)", "Technical or soft skill below 45 (+1 each)"],
        },
        "sgpa_by_sem": sgpa_by_sem, "att_by_month": att_by_month,
    }
    bundle = {"meta": meta, "students": recs, "dq": dq, "insights": insights}
    DASH.mkdir(exist_ok=True)
    (DASH / "data.js").write_text("window.SSP = " + json.dumps(bundle, separators=(",", ":")) + ";\n", encoding="utf-8")
    (OUT / "data_quality_report.json").write_text(json.dumps(dq, indent=2), encoding="utf-8")

    flat = df.drop(columns=["pillars", "drivers", "sgpa", "att_monthly", "subjects"]).copy()
    for p in PILLARS:
        flat[f"pillar_{p.lower()}"] = [r["pillars"][p] for r in recs]
    flat["reasons"] = flat["reasons"].map("; ".join)
    flat["actions"] = flat["actions"].map("; ".join)
    flat.to_csv(OUT / "student_master.csv", index=False)

    print(f"Integrated {len(df)} students from {len(dq)} sources")
    print("Score bands :", df["band"].value_counts().to_dict())
    print("Overall risk:", df["risk"].value_counts().to_dict())
    print("Academic    :", df["acad_risk"].value_counts().to_dict())
    print("Placement   :", df["plc_risk"].value_counts().to_dict())
    print("Segments    :", df["segment"].value_counts().to_dict())
    print("Wrote data/student_master.csv, data/data_quality_report.json, dashboard/data.js")


def build_insights(df, master, X):
    out = []
    c = lambda a, b: float(np.corrcoef(a, b)[0, 1])
    out.append(f"Attendance and LMS assignment completion both track CGPA closely (correlations {c(master['overall_attendance_pct'], master['cgpa']):.2f} and {c(master['assignment_completion_pct'], master['cgpa']):.2f}), so a weekly attendance + LMS report can flag trouble before exams.")
    low = df[df["att"] < 75]
    if len(low):
        hi = (low["acad_risk"] == "High").mean() * 100
        hi_o = (df[df["att"] >= 75]["acad_risk"] == "High").mean() * 100
        out.append(f"{len(low)} students are under the 75% attendance line; {hi:.0f}% of them are high academic risk versus {hi_o:.0f}% of everyone else.")
    out.append(f"Co-curricular engagement (hackathons, certifications, clubs) is associated with higher coding scores: correlation of the engagement index with coding score is {c(X['engage'], X['coding']):.2f}.")
    d = df.groupby("dept")["risk"].apply(lambda s: (s == "High").mean() * 100).sort_values(ascending=False)
    out.append(f"{d.index[0]} has the highest share of high-risk students ({d.iloc[0]:.0f}%), while {d.index[-1]} has the lowest ({d.iloc[-1]:.0f}%).")
    gap = df[df["segment"] == "Strong academics, low placement readiness"]
    if len(gap):
        out.append(f"{len(gap)} students are academically strong (avg CGPA {gap['cgpa'].mean():.1f}) but not placement-ready (avg readiness {gap['plc_ready'].mean():.0f}/100): a natural target group for a placement bootcamp.")
    final = df[(df["year"] >= 3) & (df["plc_risk"] == "High")]
    out.append(f"{len(final)} third- and fourth-year students are at high placement risk, and they are the most time-sensitive group.")
    dec = df[df["sgpa"].map(lambda v: len(v) >= 3 and v[-1] - np.mean(v[-3:-1]) <= -0.6)]
    quiet = dec[dec["cgpa"] >= 7.0]
    out.append(f"{len(dec)} students show a sharp SGPA decline, and {len(quiet)} of them still have a CGPA of 7.0 or more, so a CGPA-only report would miss them.")
    return out


if __name__ == "__main__":
    main()
