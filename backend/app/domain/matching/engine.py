# mypy: disable-error-code="no-untyped-def,no-untyped-call"
from dataclasses import dataclass

from app.db.enums import RequirementImportance, RequirementType
from app.db.models import Candidate, JobPosting

WEIGHTS = {
    "title": 15,
    "skills": 30,
    "experience": 15,
    "industry": 10,
    "education": 10,
    "location": 10,
    "language": 5,
    "certification": 5,
}


@dataclass(frozen=True, slots=True)
class MatchScore:
    scores: dict[str, float]
    matched: list[object]
    missing: list[object]
    uncertain: list[object]
    explanation: str


class RuleBasedMatchingEngine:
    version = "rule-v1"

    def calculate(self, job: JobPosting, candidate: Candidate) -> MatchScore:
        matched: list[object] = []
        missing: list[object] = []
        uncertain: list[object] = []
        requirements = {
            kind: [r for r in job.requirements if r.type is kind] for kind in RequirementType
        }
        title = self._title(
            job, candidate, requirements[RequirementType.TITLE], matched, missing, uncertain
        )
        skills = self._skills(
            candidate, requirements[RequirementType.SKILL], matched, missing, uncertain
        )
        experience = self._experience(job, candidate, matched, missing, uncertain)
        education = self._simple(
            "education",
            [e.field_of_study_normalized or e.degree or "" for e in candidate.educations],
            requirements[RequirementType.EDUCATION],
            matched,
            missing,
            uncertain,
        )
        location = self._location(
            job, candidate, requirements[RequirementType.LOCATION], matched, missing, uncertain
        )
        language = self._simple(
            "language",
            [x.language_normalized for x in candidate.languages],
            requirements[RequirementType.LANGUAGE],
            matched,
            missing,
            uncertain,
        )
        certification = self._simple(
            "certification",
            [x.name for x in candidate.certifications],
            requirements[RequirementType.CERTIFICATION],
            matched,
            missing,
            uncertain,
            neutral=True,
        )
        industry_values = [x.industry_detected or "" for x in candidate.experiences]
        industry = self._simple(
            "industry",
            industry_values,
            requirements[RequirementType.INDUSTRY],
            matched,
            missing,
            uncertain,
            neutral=True,
        )
        scores = {
            "title": title,
            "skill": skills,
            "experience": experience,
            "industry": industry,
            "education": education,
            "location": location,
            "language": language,
            "certification": certification,
        }
        total = sum(
            scores[key] * WEIGHTS["skills" if key == "skill" else key] / 100 for key in scores
        )
        scores["total"] = round(max(0.0, min(100.0, total)), 2)
        text = self._explanation(scores["total"], matched, missing, uncertain)
        return MatchScore(scores, matched, missing, uncertain, text)

    def _title(self, job, candidate, requirements, matched, missing, uncertain):
        target = self._norm(job.title)
        values = [
            candidate.current_title or "",
            candidate.headline or "",
            *(x.position_title_normalized or x.position_title_raw for x in candidate.experiences),
        ]
        values = [self._norm(v) for v in values if v]
        if not values:
            uncertain.append(
                {"category": "title", "value": target, "reason": "candidate_title_missing"}
            )
            return 0.0
        best = max((self._similarity(target, value) for value in values), default=0.0)
        (matched if best >= 70 else missing).append(
            {"category": "title", "value": job.title, "score": round(best, 1)}
        )
        return best

    def _skills(self, candidate, requirements, matched, missing, uncertain):
        if not requirements:
            return 100.0
        values = {self._norm(x.normalized_name) for x in candidate.skills}
        values.update(
            self._norm(str(skill)) for exp in candidate.experiences for skill in exp.skills_detected
        )
        if not values:
            uncertain.append({"category": "skill", "reason": "candidate_skills_missing"})
            return 0.0
        points = 0.0
        total = 0.0
        for req in requirements:
            weight = 2.0 if req.importance is RequirementImportance.REQUIRED else 1.0
            total += weight
            found = any(
                self._similarity(self._norm(req.normalized_value), value) >= 85 for value in values
            )
            (matched if found else missing).append(
                {"category": "skill", "value": req.raw_value, "importance": req.importance.value}
            )
            if found:
                points += weight
        return 100 * points / total if total else 100.0

    def _experience(self, job, candidate, matched, missing, uncertain):
        if job.min_experience_years is None:
            return 100.0
        if candidate.total_experience_months is None:
            uncertain.append(
                {
                    "category": "experience",
                    "value": job.min_experience_years,
                    "reason": "candidate_duration_missing",
                }
            )
            return 0.0
        actual = candidate.total_experience_months / 12
        score = min(100.0, 100 * actual / max(job.min_experience_years, 0.1))
        (matched if actual >= job.min_experience_years else missing).append(
            {
                "category": "experience",
                "required_years": job.min_experience_years,
                "candidate_years": round(actual, 1),
            }
        )
        return score

    def _location(self, job, candidate, requirements, matched, missing, uncertain):
        if not requirements and not job.city and not job.country:
            return 100.0
        target_city = self._norm(
            job.city or (requirements[0].normalized_value if requirements else "")
        )
        candidate_city = self._norm(candidate.city or "")
        if not candidate_city:
            uncertain.append({"category": "location", "reason": "candidate_location_missing"})
            return 0.0
        if target_city and candidate_city == target_city:
            matched.append({"category": "location", "value": candidate.city})
            return 100.0
        if job.country and self._norm(candidate.country or "") == self._norm(job.country):
            matched.append({"category": "location", "value": candidate.country, "partial": True})
            return 60.0
        missing.append({"category": "location", "value": job.city or job.country})
        return 0.0

    def _simple(self, category, values, requirements, matched, missing, uncertain, neutral=False):
        if not requirements:
            return 100.0
        normalized = [self._norm(v) for v in values if v]
        if not normalized:
            uncertain.append({"category": category, "reason": f"candidate_{category}_missing"})
            return 0.0
        found = 0
        for req in requirements:
            ok = any(
                self._similarity(self._norm(req.normalized_value), value) >= 80
                for value in normalized
            )
            (matched if ok else missing).append({"category": category, "value": req.raw_value})
            found += int(ok)
        return 100 * found / len(requirements)

    @staticmethod
    def _norm(value):
        return " ".join(
            value.casefold()
            .replace("software developer", "software engineer")
            .replace("developer", "engineer")
            .split()
        )

    @staticmethod
    def _similarity(left, right):
        if left == right:
            return 100.0
        a, b = set(left.split()), set(right.split())
        return 100 * len(a & b) / len(a | b) if a and b else 0.0

    @staticmethod
    def _explanation(total, matched, missing, uncertain):
        strong = (
            ", ".join(str(x.get("value", x.get("category"))) for x in matched[:3])
            or "No strong matches"
        )
        absent = ", ".join(str(x.get("value", x.get("category"))) for x in missing[:3]) or "none"
        unsure = ", ".join(str(x.get("category")) for x in uncertain[:2]) or "none"
        return (
            f"Total fit: %{round(total)}. Matched: {strong}. "
            f"Missing: {absent}. Uncertain: {unsure}."
        )
