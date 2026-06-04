/** Public surface of the jars recommendation engine (browser port). */

export { Dataset } from "./dataset";
export type { ProgramGroup } from "./dataset";
export { recommend } from "./recommend";
export { feasibility } from "./scoring";
export { bandInRange, bandYears } from "./types";
export type { Cutoff, Recommendation, RawDataset, RecommendParams } from "./types";
export * from "./constants";
