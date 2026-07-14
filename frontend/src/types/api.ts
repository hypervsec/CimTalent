export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};
export type Job = {
  id: string;
  title: string;
  company_name: string;
  city?: string | null;
  status: string;
  created_at: string;
  requirement_count?: number;
  search_query_count?: number;
  candidate_match_count?: number;
  shortlist_count?: number;
  description_raw?: string;
  country?: string | null;
};
export type Candidate = {
  id: string;
  full_name?: string | null;
  headline?: string | null;
  city?: string | null;
  current_title?: string | null;
  current_company?: string | null;
  source: string;
  profile_status: string;
  data_quality_score: number;
  primary_profile_url?: string | null;
};
export type Match = {
  id: string;
  candidate_name?: string | null;
  total_score: number;
  title_score: number;
  skill_score: number;
  experience_score: number;
  education_score: number;
  location_score: number;
  explanation?: string | null;
  matched_requirements: object[];
  missing_requirements: object[];
  uncertain_requirements: object[];
};
export type Shortlist = {
  id: string;
  status: string;
  recruiter_note?: string | null;
  candidate: Candidate;
  match?: Match | null;
  updated_at: string;
};
