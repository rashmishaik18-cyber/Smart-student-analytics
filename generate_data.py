"""
generate_data.py
Creates realistic, deliberately MESSY synthetic college data in data/raw/ so the
pipeline has real integration + cleaning work to do.

Sources (one CSV each): academic, academic_semesters, subject_marks, attendance,
attendance_monthly, lms, engagement, placement, skills, feedback.

Messiness injected: inconsistent ID formats, department spelling variants,
duplicate rows, missing values, out-of-range values, CGPA on a % scale,
students absent from some sources, and orphan IDs that don't exist in academic.
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
RAW = Path(__file__).parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
N = 600

FIRST = ["Aarav","Vivaan","Aditya","Sai","Arjun","Rohan","Karthik","Rahul","Ishaan","Kiran","Ananya","Diya","Sneha",
         "Priya","Kavya","Meera","Nisha","Pooja","Riya","Lakshmi","Harsha","Varun","Teja","Manoj","Deepak","Swathi",
         "Bhavya","Charan","Divya","Naveen"]
LAST = ["Reddy","Sharma","Rao","Naidu","Patel","Kumar","Singh","Varma","Gupta","Iyer","Nair","Chowdary","Das","Joshi",
        "Menon","Mishra","Yadav","Prasad","Goud","Raju","Shetty","Verma","Pillai","Bose","Khan","Ali","Fernandes",
        "Thomas","Desai","Kulkarni"]
DEPTS = ["CSE", "IT", "ECE", "MECH", "CIVIL"]
DEPT_P = [.28, .17, .20, .18, .17]
DEPT_ABILITY = {"CSE": .10, "IT": .05, "ECE": 0, "MECH": -.10, "CIVIL": -.05}
DEPT_CODING = {"CSE": 10, "IT": 8, "ECE": 0, "MECH": -8, "CIVIL": -9}
DEPT_VARIANTS = {
    "CSE": ["cse", "Computer Science", "C.S.E", "Comp Sci"],
    "IT": ["it", "Information Technology", "Info Tech"],
    "ECE": ["ece", "Electronics", "E.C.E"],
    "MECH": ["mech", "Mechanical", "Mech."],
    "CIVIL": ["civil", "Civil Engg"],
}
SUBJECTS = ["Mathematics", "Core Theory I", "Core Theory II", "Laboratory", "Elective"]
MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ids = [f"S{i:04d}" for i in range(1, N + 1)]
dept = rng.choice(DEPTS, N, p=DEPT_P)
year = rng.choice([1, 2, 3, 4], N)
names = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(N)]

ability = rng.normal(0, 1, N) + np.array([DEPT_ABILITY[d] for d in dept])
effort = .4 * ability + .92 * rng.normal(0, 1, N)
career = .3 * effort + .95 * rng.normal(0, 1, N)
coding_off = np.array([DEPT_CODING[d] for d in dept])

# Student archetypes that give the analytics something real to find
u = rng.random(N)
disengaged = u < .12
gap = (u >= .12) & (u < .24)            # academically strong, low placement drive
placefocus = (u >= .24) & (u < .31)     # placement-minded, academically weak
decliner = (rng.random(N) < .09) & (year >= 2)
effort = np.where(disengaged, effort - 1.2, effort)
ability = np.where(gap, ability + .9, np.where(placefocus, ability - .9, ability))
career = np.where(gap, career - 1.3, np.where(placefocus, career + 1.0, np.where(disengaged, career - .6, career)))

clip = np.clip

# ---------- academic ----------
sems_done = 2 * year - 1
slope = rng.normal(0, .08, N)
slope = np.where(decliner, -.45, slope)
sem_rows, cgpa = [], np.zeros(N)
for i in range(N):
    vals = []
    for s in range(1, sems_done[i] + 1):
        v = 7.4 + .8 * ability[i] + .45 * effort[i] + .3 * rng.normal() + slope[i] * (s - 1)
        v = float(clip(v, 3.0, 10.0))
        vals.append(v)
        sem_rows.append((ids[i], s, round(v, 2)))
    cgpa[i] = round(float(np.mean(vals)), 2)
b = rng.poisson(clip(.55 - .5 * ability - .3 * effort, .02, 3))
backlogs = np.where(year == 1, np.minimum(b, 1) * (rng.random(N) < .4), np.minimum(b, 6)).astype(int)
internal = clip(65 + 10 * ability + 5 * effort + rng.normal(0, 7, N), 20, 98).round(1)
academic = pd.DataFrame({"student_id": ids, "name": names, "department": dept, "year": year,
                         "cgpa": cgpa, "internal_marks_avg": internal, "backlogs": backlogs})
sem = pd.DataFrame(sem_rows, columns=["student_id", "semester", "sgpa"])
sub_rows = []
for i in range(N):
    for sname in SUBJECTS:
        sub_rows.append((ids[i], sname, round(float(clip(internal[i] + rng.normal(0, 9), 15, 100)), 1)))
subjects = pd.DataFrame(sub_rows, columns=["student_id", "subject", "marks"])

# ---------- attendance ----------
base = clip(85 + 7 * effort + 3 * ability + rng.normal(0, 5, N), 35, 99)
drift = np.where(disengaged, -2.6, rng.normal(0, .5, N))
att_rows = []
overall = np.zeros(N)
for i in range(N):
    m = [float(clip(base[i] + rng.normal(0, 4) + drift[i] * k, 20, 100)) for k in range(len(MONTHS))]
    overall[i] = np.mean(m)
    for mo, v in zip(MONTHS, m):
        att_rows.append((ids[i], mo, round(v, 1)))
att_month = pd.DataFrame(att_rows, columns=["student_id", "month", "attendance_pct"])
low_pct = clip(overall - np.abs(rng.normal(0, 7, N)) - 3, 15, 100).round(1)
attendance = pd.DataFrame({"student_id": ids, "overall_attendance_pct": overall.round(1),
                           "lowest_subject_pct": low_pct,
                           "lowest_subject": rng.choice(SUBJECTS, N)})

# ---------- LMS ----------
lms = pd.DataFrame({
    "student_id": ids,
    "logins_per_week": clip(rng.poisson(clip(6 + 3 * effort + ability, 0.5, 20)), 0, 20),
    "assignment_completion_pct": clip(78 + 12 * effort + 6 * ability + rng.normal(0, 10, N), 5, 100).round(1),
    "avg_session_minutes": clip(25 + 8 * effort + rng.normal(0, 8, N), 3, 90).round(1),
})

# ---------- engagement ----------
dis = np.where(disengaged, -.7, 0)
engagement = pd.DataFrame({
    "student_id": ids,
    "events_attended": clip(rng.poisson(np.exp(1.3 + .35 * career + .2 * effort + dis)), 0, 20),
    "clubs": clip(rng.poisson(np.exp(.4 + .3 * career + dis)), 0, 6),
    "hackathons": clip(rng.poisson(np.exp(-.5 + .5 * career + (coding_off > 0) * .3 + dis)), 0, 8),
    "certifications": clip(rng.poisson(np.exp(.3 + .4 * career + .15 * effort + dis)), 0, 10),
})

# ---------- placement + skills ----------
placement = pd.DataFrame({
    "student_id": ids,
    "aptitude_score": clip(62 + 9 * ability + 7 * career + 5 * effort + rng.normal(0, 9, N), 5, 99).round(1),
    "coding_score": clip(56 + 8 * ability + 10 * career + coding_off + rng.normal(0, 10, N), 0, 99).round(1),
    "mock_interview_score": clip(60 + 6 * ability + 11 * career + rng.normal(0, 10, N), 5, 99).round(1),
    "mock_interviews_attended": rng.poisson(np.exp(.6 + .4 * career)),
})
skills = pd.DataFrame({
    "student_id": ids,
    "technical_skill": clip(63 + 7 * ability + 7 * career + .6 * coding_off + rng.normal(0, 8, N), 10, 99).round(1),
    "soft_skill": clip(65 + 5 * effort + 8 * career + rng.normal(0, 9, N), 10, 99).round(1),
})
feedback = pd.DataFrame({
    "student_id": ids,
    "satisfaction": clip(3.5 + .35 * effort + .2 * ability + rng.normal(0, .7, N), 1, 5).round(1),
    "faculty_rating": clip(3.3 + .5 * effort + .3 * ability + rng.normal(0, .5, N), 1, 5).round(1),
})


# ---------- inject mess ----------
def dirty_ids(df):
    arr = df["student_id"].astype(str).values.copy()
    for i in rng.choice(len(arr), int(.04 * len(arr)), replace=False):
        v = arr[i]
        arr[i] = [v.lower(), f" {v} ", "S-" + v[1:]][rng.integers(0, 3)]
    df["student_id"] = arr
    return df


def add_missing(df, cols, frac=.04):
    for c in cols:
        df[c] = df[c].astype(float)
        df.loc[rng.random(len(df)) < frac, c] = np.nan
    return df


def add_dupes(df, frac=.02):
    return pd.concat([df, df.sample(int(frac * len(df)), random_state=int(rng.integers(0, 9999)))], ignore_index=True)


def add_orphans(df, n=3):
    extra = df.sample(n, random_state=1).copy()
    extra["student_id"] = [f"S{9001 + k}" for k in range(n)]
    return pd.concat([df, extra], ignore_index=True)


def drop_students(df, frac):
    return df[rng.random(len(df)) > frac]


def finish(df, name, cols=None, drop=0.0, orphans=True, dupes=True, key_dirty=True):
    if drop:
        df = drop_students(df, drop)
    if cols:
        df = add_missing(df, cols)
    if dupes:
        df = add_dupes(df)
    if orphans:
        df = add_orphans(df)
    if key_dirty:
        df = dirty_ids(df.reset_index(drop=True))
    df.sample(frac=1, random_state=3).to_csv(RAW / name, index=False)
    print(f"  wrote {name:<24}{len(df):>6} rows")


# academic: dept/year spelling mess + % scale CGPA
academic = academic.copy()
academic["department"] = [rng.choice(DEPT_VARIANTS[d]) if rng.random() < .25 else d for d in academic["department"]]
academic["year"] = [f"Year {y}" if rng.random() < .03 else (f"{y}nd" if rng.random() < .03 else y) for y in academic["year"]]
pct = rng.random(N) < .01
academic.loc[pct, "cgpa"] = (academic.loc[pct, "cgpa"] * 10).round(1)
academic = add_missing(academic, ["cgpa", "internal_marks_avg"], .02)
att_out = rng.random(N) < .012
attendance.loc[att_out, "overall_attendance_pct"] = attendance.loc[att_out, "overall_attendance_pct"] + 6
bad_apt = rng.random(N) < .012
placement.loc[bad_apt, "aptitude_score"] = -1

print("Writing raw sources to", RAW)
finish(academic, "academic.csv", orphans=False)
finish(sem, "academic_semesters.csv", key_dirty=True, orphans=True)
finish(subjects, "subject_marks.csv")
finish(attendance, "attendance.csv", ["lowest_subject_pct"], drop=.02)
finish(att_month, "attendance_monthly.csv")
finish(lms, "lms.csv", ["logins_per_week", "assignment_completion_pct"], drop=.03)
finish(engagement, "engagement.csv", ["events_attended", "hackathons"], drop=.03)
# freshers are mostly not assessed yet -> realistic gaps
placement = placement[~((pd.Series(year) == 1).values & (rng.random(N) < .55))]
finish(placement, "placement.csv", ["coding_score", "mock_interview_score"])
finish(skills, "skills.csv", ["technical_skill"], drop=.02)
finish(feedback, "feedback.csv", ["satisfaction"], drop=.04)
print("Done.")
