/** Regions + organ systems for the clinical anatomy panel. */

export type BodyRegionId =
  | "head"
  | "neck"
  | "chest"
  | "abdomen"
  | "pelvis"
  | "left_arm"
  | "right_arm"
  | "left_leg"
  | "right_leg"
  | "back";

export type OrganSystemId =
  | "nervous"
  | "cardiovascular"
  | "respiratory"
  | "digestive"
  | "endocrine"
  | "musculoskeletal"
  | "urinary";

export const REGION_LABELS: Record<BodyRegionId, { en: string; hi: string }> = {
  head: { en: "Head", hi: "सिर" },
  neck: { en: "Neck", hi: "गर्दन" },
  chest: { en: "Chest", hi: "छाती" },
  abdomen: { en: "Abdomen", hi: "पेट" },
  pelvis: { en: "Pelvis", hi: "कमर" },
  left_arm: { en: "Left arm", hi: "बायाँ हाथ" },
  right_arm: { en: "Right arm", hi: "दायाँ हाथ" },
  left_leg: { en: "Left leg", hi: "बायाँ पैर" },
  right_leg: { en: "Right leg", hi: "दायाँ पैर" },
  back: { en: "Back", hi: "पीठ" },
};

export const SYSTEM_LABELS: Record<OrganSystemId, { en: string; hi: string }> = {
  nervous: { en: "Nervous", hi: "तंत्रिका" },
  cardiovascular: { en: "Heart / vessels", hi: "हृदय / रक्तवाहिका" },
  respiratory: { en: "Lungs", hi: "श्वसन" },
  digestive: { en: "Digestive", hi: "पाचन" },
  endocrine: { en: "Hormones", hi: "अंतःस्रावी" },
  musculoskeletal: { en: "Bones / muscle", hi: "हड्डी / मांसपेशी" },
  urinary: { en: "Urinary", hi: "मूत्र" },
};

const REGION_RULES: { region: BodyRegionId; pattern: RegExp }[] = [
  { region: "head", pattern: /\b(head|forehead|temple|migraine|skull)\b|सिर|माथा|कान|आँख|आंख|चेहरा/i },
  { region: "neck", pattern: /\b(neck|throat)\b|गर्दन|गला/i },
  { region: "chest", pattern: /\b(chest|breast|rib)\b|छाती|सीना|पसल/i },
  { region: "abdomen", pattern: /\b(abdomen|stomach|belly|liver|gut)\b|पेट|उदर|अमाशय/i },
  { region: "pelvis", pattern: /\b(pelvis|hip|groin)\b|कमर|निचला\s*पेट|कूल्हा/i },
  { region: "back", pattern: /\b(back|spine|lumbar)\b|पीठ|रीढ़/i },
  {
    region: "left_arm",
    pattern: /\b(left\s+arm|left\s+hand|left\s+shoulder)\b|बायाँ?\s*(हाथ|बांह|कंधा)/i,
  },
  {
    region: "right_arm",
    pattern: /\b(right\s+arm|right\s+hand|right\s+shoulder)\b|दायाँ?\s*(हाथ|बांह|कंधा)/i,
  },
  {
    region: "left_leg",
    pattern: /\b(left\s+leg|left\s+foot|left\s+knee)\b|बायाँ?\s*(पैर|टांग|घुटना)/i,
  },
  {
    region: "right_leg",
    pattern: /\b(right\s+leg|right\s+foot|right\s+knee)\b|दायाँ?\s*(पैर|टांग|घुटना)/i,
  },
];

const SYSTEM_RULES: { system: OrganSystemId; pattern: RegExp; regions?: BodyRegionId[] }[] = [
  {
    system: "cardiovascular",
    pattern:
      /\b(heart|cardiac|blood\s*pressure|bp|hypertension|chest\s*pain|palpitation)\b|दिल|हृदय|ब्लड\s*प्रेशर|बी\.?\s*पी|सीने\s*में\s*दर्द|धड़कन/i,
    regions: ["chest", "left_arm"],
  },
  {
    system: "respiratory",
    pattern: /\b(lung|breath|asthma|cough|wheeze|respiratory)\b|साँस|सांस|दम|अस्थमा|खाँसी|खांसी|फेफड/i,
    regions: ["chest"],
  },
  {
    system: "digestive",
    pattern:
      /\b(stomach|digest|nausea|vomit|diarrh|constipation|appetite|acidity)\b|पेट|उल्टी|दस्त|कब्ज|भूख|एसिडिटी|पाचन/i,
    regions: ["abdomen"],
  },
  {
    system: "endocrine",
    pattern: /\b(diabetes|sugar|thyroid|hormone|insulin)\b|शुगर|मधुमेह|डायबिटीज|थायरॉइड|थायराइड/i,
    regions: ["abdomen", "neck"],
  },
  {
    system: "nervous",
    pattern:
      /\b(nerve|neuro|migraine|seizure|numb|tingl|stroke|paralysis|dizziness|vertigo)\b|सिर\s*दर्द|मिरगी|सुन्न|झनझना|लकवा|चक्कर|तंत्रिका/i,
    regions: ["head", "back"],
  },
  {
    system: "musculoskeletal",
    pattern: /\b(bone|joint|muscle|fracture|arthritis|sprain)\b|हड्डी|जोड़|मांसपेशी|मोच|गठिया/i,
    regions: ["back", "right_leg", "right_arm"],
  },
  {
    system: "urinary",
    pattern: /\b(urine|urinary|kidney|bladder|uti)\b|मूत्र|पेशाब|गुर्दा|किडनी/i,
    regions: ["pelvis", "abdomen"],
  },
];

export function detectBodyRegions(text: string): BodyRegionId[] {
  if (!text?.trim()) return [];
  const found = new Set<BodyRegionId>();
  for (const rule of REGION_RULES) {
    if (rule.pattern.test(text)) found.add(rule.region);
  }
  for (const rule of SYSTEM_RULES) {
    if (rule.pattern.test(text) && rule.regions) {
      for (const r of rule.regions) found.add(r);
    }
  }
  return [...found];
}

export function detectOrganSystems(text: string): OrganSystemId[] {
  if (!text?.trim()) return [];
  const found = new Set<OrganSystemId>();
  for (const rule of SYSTEM_RULES) {
    if (rule.pattern.test(text)) found.add(rule.system);
  }
  return [...found];
}

export function mergeRegions(
  current: BodyRegionId[],
  next: BodyRegionId[],
): BodyRegionId[] {
  return [...new Set([...current, ...next])];
}

export function mergeSystems(
  current: OrganSystemId[],
  next: OrganSystemId[],
): OrganSystemId[] {
  return [...new Set([...current, ...next])];
}
