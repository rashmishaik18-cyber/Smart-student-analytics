# Student Success Score: short note

## What it is
A single 0-100 number per student that combines academic, attendance, LMS,
engagement, placement, skills and feedback signals. It is a **weighted sum of 16
indicators**, each first converted to a 0-100 scale.

## Indicators and weights
| Pillar (total) | Indicator | Weight | How it is put on 0-100 |
|---|---|---|---|
| Academic (35%) | CGPA | 16% | CGPA x 10 |
| | Internal assessment marks | 9% | average internal marks /100 |
| | Backlog-free record | 7% | 100 - 25 per backlog (floor 0) |
| | Average subject marks | 3% | mean of subject marks |
| Attendance (15%) | Overall attendance | 10% | attendance % |
| | Lowest-subject attendance | 5% | lowest subject % |
| LMS (10%) | Login frequency | 4% | logins/week, 10 per week = 100 |
| | Assignment completion | 6% | completion % |
| Engagement (10%) | Co-curricular index | 10% | 30% events (8 = full), 20% clubs (3), 25% hackathons (3), 25% certifications (4) |
| Placement (20%) | Aptitude | 6% | score /100 |
| | Coding | 8% | score /100 |
| | Mock interview | 6% | score /100 |
| Skills (5%) | Technical / Soft | 3% / 2% | assessment score /100 |
| Feedback (5%) | Satisfaction / Faculty rating | 2% / 3% | (rating - 1) / 4 x 100 |

`Score = sum(weight x indicator)`. Bands: Excellent 75+, Good 60-74, Watch 45-59, Critical <45.

Why these weights: academic standing carries the most weight because it is what
the college is accountable for; placement readiness is next because it is the
main outcome for final-year students; the remaining pillars are leading
indicators that usually move before grades do. **The weights are a starting
proposal for faculty to tune** (they sit in one list, `INDICATORS`, in `pipeline.py`).

## Explainability
For every student, each indicator's contribution is shown as
`weight x (student value - campus average)`, in score points. The profile drawer
plots these as green (helping) and red (hurting) bars, so you can see exactly why a
score is high or low.

## Risk flags (separate from the score)
Risk uses a transparent points system, so each flag comes with plain-language reasons
and suggested actions.
- **Academic risk**: CGPA < 6 (+3) / < 7 (+1); 3+ backlogs (+3) / 1-2 (+1); attendance < 65% (+3) / < 75% (+2);
  internal marks < 50 (+2) / < 60 (+1); SGPA drop of 0.6+ (+2); assignments < 50% (+1). High at 7+, Medium at 3+.
- **Placement risk**: readiness (30% aptitude + 40% coding + 30% mock) < 50 (+3) / < 60 (+1); coding < 40 (+2);
  aptitude < 50 (+1); mock < 45 (+1); CGPA < 6 cut-off (+2); active backlog (+1); low engagement (+1);
  technical or soft skill < 45 (+1 each). High at 8+, Medium at 4+.
- Overall risk is the higher of the two.

## Segments (rule-based, each tied to an action)
Needs urgent support; Strong academics but low placement readiness; Placement-ready
but academics slipping; Disengaged; Star performers; Steady middle.

## Limits to be honest about
- The bundled data is **synthetic**. Relationships in the insights (for example attendance vs CGPA) were
  built into the generator, so they demonstrate the method, not real campus findings.
- Thresholds (6.0 CGPA, 75% attendance) are common defaults; adjust to your institution's rules.
- There are no historical outcome labels here, so the score is a rule-based index, not a trained predictive
  model. With real outcomes (dropouts, placements) the same indicators could feed a supervised model and the
  weights could be validated against it.
- Missing values are filled with the department-and-year median; each student's data completeness is shown.
