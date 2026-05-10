export type UserRole = "admin" | "parent" | "child";

export interface User {
  id: number;
  email: string | null;
  name: string;
  role: UserRole;
  family_id: number | null;
  profile_picture_url: string | null;
  birthdate: string | null;
  parent_user_id: number | null;
}

export interface AttendeeSummary {
  user_id: number;
  name: string;
  role: "admin" | "parent" | "child";
  family_id: number | null;
  family_name: string | null;
  profile_picture_url: string | null;
  days_attended: number;
}

export interface Family {
  id: number;
  name: string;
  profile_picture_url: string | null;
  created_at: string;
  members: User[];
}

export type EventStatus =
  | "planlagt"
  | "aabent"
  | "deltagelse_laast"
  | "afsluttet";

export interface Chor {
  id: number;
  meal: "morgenmad" | "frokost" | "aftensmad";
  action: "forberedelse" | "oprydning";
  assignee_user_id: number | null;
}

export interface Activity {
  id: number;
  name: string;
  description: string | null;
  time: string | null;
  created_by_user_id: number | null;
  attendee_user_ids: number[];
}

export interface EventDay {
  id: number;
  date: string;
  chors: Chor[];
  activities: Activity[];
  attendee_user_ids: number[];
  bed_demand: number;
}

export interface BedDemand {
  bed_count: number | null;
  peak: number;
  peak_date: string | null;
}

export interface KarkovEvent {
  id: number;
  name: string;
  description: string | null;
  address: string | null;
  location_url: string | null;
  summerhouse_url: string | null;
  summerhouse_title: string | null;
  summerhouse_summary: string | null;
  summerhouse_image_url: string | null;
  summerhouse_scraped_at: string | null;
  start_date: string;
  end_date: string;
  host_user_id: number | null;
  status: EventStatus;
  bed_count: number | null;
  created_at: string;
  days: EventDay[];
  bed_demand: BedDemand;
  attendees: AttendeeSummary[];
}

export interface ExpenseCategory {
  id: number;
  name: string;
  is_per_person: boolean;
  is_per_night: boolean;
  is_utility: boolean;
}

export interface Expense {
  id: number;
  event_id: number;
  category_id: number;
  chor_id: number | null;
  paid_by_user_id: number;
  paid_by_user_name: string | null;
  amount_cents: number;
  description: string | null;
  created_at: string;
}

export interface UserShare {
  user_id: number;
  family_id: number;
  paid_cents: number;
  share_cents: number;
  net_cents: number;
}

export interface Settlement {
  from_family_id: number;
  to_family_id: number;
  amount_cents: number;
}

export interface Budget {
  event_id: number;
  is_final: boolean;
  total_cents: number;
  per_category_cents: Record<number, number>;
  shares: UserShare[];
  settlements: Settlement[];
  family_names: Record<number, string>;
}

export interface Invite {
  id: number;
  email: string;
  family_id: number;
  token: string;
  expires_at: string;
  notified_at: string | null;
  used_at: string | null;
}

export interface InviteSendResult {
  sent: number;
  invites: Invite[];
}

export interface PricingRules {
  baby_max_age: number;
  kid_max_age: number;
}

export type ChatKind = "user" | "system";

export interface ChatMessage {
  id: number;
  kind: ChatKind;
  user_id: number | null;
  user_name: string | null;
  body: string;
  related_event_id: number | null;
  icon: string | null;
  created_at: string;
}

export interface NotifyPref {
  notify_email: boolean | null;
  notify_prompted_at: string | null;
  needs_prompt: boolean;
}
