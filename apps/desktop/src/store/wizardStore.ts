import { create } from "zustand";

export interface ModelConfig {
  provider: string | null;
  endpoint: string;
  modelName: string;
  skip: boolean;
  privacyAccepted: boolean;
}

export interface DomainDraft {
  intent: string;
  facets: string[];
  boundaryAnswers: Record<string, string>;
  rootCategories: string[];
  depth: number;
}

export interface BuildProgress {
  stage: string;
  percent: number;
  message: string;
}

export interface WizardState {
  step: number;
  projectName: string;
  projectDir: string;
  sourcePath: string;
  sourceInspection: any;
  metadataBuilt: boolean;
  modelConfig: ModelConfig;
  domainDraft: DomainDraft;
  domainPath: string;
  domainLockPath: string;
  previewData: any;
  buildJobId: string | null;
  buildProgress: BuildProgress;
  buildReport: any;
  logs: string[];

  setStep: (step: number) => void;
  setProjectInfo: (name: string, dir: string) => void;
  setSourceInfo: (path: string, inspection: any) => void;
  setMetadataBuilt: (built: boolean) => void;
  setModelConfig: (config: Partial<ModelConfig>) => void;
  setDomainDraft: (draft: Partial<DomainDraft>) => void;
  setDomainPath: (path: string) => void;
  setDomainLockPath: (path: string) => void;
  setPreviewData: (data: any) => void;
  setBuildJobId: (id: string | null) => void;
  setBuildProgress: (progress: BuildProgress) => void;
  setBuildReport: (report: any) => void;
  addLog: (log: string) => void;
  clearLogs: () => void;
}

export const useWizardStore = create<WizardState>((set) => ({
  step: 1,
  projectName: "MyWikis",
  projectDir: "",
  sourcePath: "",
  sourceInspection: null,
  metadataBuilt: false,
  modelConfig: {
    provider: null,
    endpoint: "http://localhost:11434",
    modelName: "llama3",
    skip: false,
    privacyAccepted: false,
  },
  domainDraft: {
    intent: "",
    facets: [],
    boundaryAnswers: {},
    rootCategories: ["Video_games"],
    depth: 6,
  },
  domainPath: "",
  domainLockPath: "",
  previewData: null,
  buildJobId: null,
  buildProgress: { stage: "IDLE", percent: 0, message: "" },
  buildReport: null,
  logs: [],

  setStep: (step) => set({ step }),
  setProjectInfo: (name, dir) => set({ projectName: name, projectDir: dir }),
  setSourceInfo: (path, inspection) => set({ sourcePath: path, sourceInspection: inspection }),
  setMetadataBuilt: (built) => set({ metadataBuilt: built }),
  setModelConfig: (config) =>
    set((state) => ({ modelConfig: { ...state.modelConfig, ...config } })),
  setDomainDraft: (draft) =>
    set((state) => ({ domainDraft: { ...state.domainDraft, ...draft } })),
  setDomainPath: (path) => set({ domainPath: path }),
  setDomainLockPath: (path) => set({ domainLockPath: path }),
  setPreviewData: (data) => set({ previewData: data }),
  setBuildJobId: (id) => set({ buildJobId: id }),
  setBuildProgress: (progress) => set({ buildProgress: progress }),
  setBuildReport: (report) => set({ buildReport: report }),
  addLog: (log) => set((state) => ({ logs: [...state.logs.slice(-4999), log] })),
  clearLogs: () => set({ logs: [] }),
}));
