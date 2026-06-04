/** Canonical vocabularies, mirrored from jars-cli/src/jars_lib/constants.py.
 *
 * Keep these byte-identical to the Python labels — they are matched against the dataset's
 * dictionary values, which come straight from the JoSAA source via the same constants.
 */

export const INSTITUTE_TYPES = ["IIT", "NIT", "IIIT", "GFTI"] as const;
export type InstituteType = (typeof INSTITUTE_TYPES)[number];

// JoSAA uses JEE Advanced ranks for IIT allocation and JEE Mains (CRL) ranks for the rest.
export const IIT_TYPES: ReadonlySet<string> = new Set(["IIT"]);
export const NON_IIT_TYPES: ReadonlySet<string> = new Set(["NIT", "IIIT", "GFTI"]);

export const SEAT_TYPES = [
  "OPEN",
  "OPEN (PwD)",
  "EWS",
  "EWS (PwD)",
  "OBC-NCL",
  "OBC-NCL (PwD)",
  "SC",
  "SC (PwD)",
  "ST",
  "ST (PwD)",
] as const;

export const GENDER_NEUTRAL = "Gender-Neutral";
export const GENDER_FEMALE = "Female-only (including Supernumerary)";

// Quota labels: IITs use "AI"; NIT/IIIT/GFTI use HS/OS (plus a few special quotas).
export const QUOTA_ALL_INDIA = "AI";
export const QUOTA_HOME_STATE = "HS";
export const QUOTA_OTHER_STATE = "OS";

export const INDIAN_STATES = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jammu and Kashmir",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Ladakh",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  // Union Territories
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Lakshadweep",
  "Puducherry",
] as const;
