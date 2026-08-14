export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id?: number | string | null;
  method: string;
  params?: Record<string, any>;
}

export interface JsonRpcResponse<T = any> {
  jsonrpc: "2.0";
  id?: number | string | null;
  result?: T;
  error?: {
    code: number;
    message: string;
    data?: {
      code: string;
      message: string;
      detail?: Record<string, any>;
    };
  };
}

export const PROTOCOL_METHODS = [
  "engine.hello",
  "project.create",
  "project.open",
  "project.get",
  "source.inspect",
  "metadata.build",
  "metadata.search",
  "model.detect",
  "model.add",
  "model.list",
  "model.test",
  "domain.create",
  "domain.proposeFacets",
  "domain.boundaryQuestions",
  "domain.applyAnswers",
  "domain.compile",
  "domain.resolveReviews",
  "domain.preview",
  "domain.explain",
  "build.start",
  "build.resume",
  "build.cancel",
  "build.status",
  "corpus.validate",
  "export.markdown",
  "export.jsonl",
  "purge.plan",
  "purge.confirm",
  "job.subscribe",
] as const;

export type ProtocolMethod = (typeof PROTOCOL_METHODS)[number];

export class EngineClient {
  private requestId = 0;
  private invokeHandler: (method: string, params: Record<string, any>) => Promise<any>;

  constructor(invokeHandler?: (method: string, params: Record<string, any>) => Promise<any>) {
    this.invokeHandler = invokeHandler || (async (_m, _p) => ({ status: "mocked" }));
  }

  async call<T = any>(method: ProtocolMethod, params: Record<string, any> = {}): Promise<T> {
    this.requestId += 1;
    return this.invokeHandler(method, params);
  }

  async hello() {
    return this.call("engine.hello", { client_version: "0.1.0" });
  }

  async createProject(name: string, projectDir: string) {
    return this.call("project.create", { name, project_dir: projectDir });
  }

  async openProject(projectDir: string) {
    return this.call("project.open", { project_dir: projectDir });
  }

  async getProject(projectDir: string) {
    return this.call("project.get", { project_dir: projectDir });
  }

  async inspectSource(sourcePath: string) {
    return this.call("source.inspect", { source: sourcePath });
  }

  async buildMetadata(sourcePath: string, projectDir: string) {
    return this.call("metadata.build", { source: sourcePath, project_dir: projectDir });
  }

  async searchMetadata(projectDir: string, query: string) {
    return this.call("metadata.search", { project_dir: projectDir, query });
  }

  async detectModels() {
    return this.call("model.detect");
  }

  async addModel(url: string, provider?: string) {
    return this.call("model.add", { url, provider });
  }

  async listModels() {
    return this.call("model.list");
  }

  async testModel(provider: string, endpoint: string, modelName: string) {
    return this.call("model.test", { provider, endpoint, model: modelName });
  }

  async proposeFacets(intent: string, provider?: string) {
    return this.call("domain.proposeFacets", { intent, provider });
  }

  async boundaryQuestions(intent: string, facets: Record<string, any>) {
    return this.call("domain.boundaryQuestions", { intent, facets });
  }

  async createDomain(
    projectDir: string,
    opts: { name: string; language: string; intent?: string; roots: string[]; maxDepth: number; facets?: string[] },
  ) {
    return this.call("domain.create", {
      project_dir: projectDir,
      name: opts.name,
      language: opts.language,
      intent: opts.intent,
      roots: opts.roots,
      max_depth: opts.maxDepth,
      facets: opts.facets,
    });
  }

  async compileDomain(domainPath: string, projectDir: string) {
    return this.call("domain.compile", { domain: domainPath, project_dir: projectDir });
  }

  async previewDomain(domainPath: string, projectDir: string) {
    return this.call("domain.preview", { domain: domainPath, project_dir: projectDir });
  }

  async explainDomain(domainPath: string, projectDir: string, pageTitle: string) {
    return this.call("domain.explain", { domain: domainPath, project_dir: projectDir, page_title: pageTitle });
  }

  async startBuild(domainPath: string, projectDir: string, outputDir: string, allowLowDisk = false, resume = false) {
    return this.call("build.start", {
      domain: domainPath,
      project_dir: projectDir,
      output: outputDir,
      allow_low_disk: allowLowDisk,
      resume,
    });
  }

  async resumeBuild(domainPath: string, projectDir: string, outputDir: string, jobId: string) {
    return this.call("build.resume", {
      domain: domainPath,
      project_dir: projectDir,
      output: outputDir,
      job_id: jobId,
    });
  }

  async cancelBuild(jobId: string) {
    return this.call("build.cancel", { job_id: jobId });
  }

  async validateCorpus(corpusPath: string) {
    return this.call("corpus.validate", { corpus: corpusPath });
  }

  async exportMarkdown(corpusPath: string, outputDir: string) {
    return this.call("export.markdown", { corpus: corpusPath, output: outputDir });
  }

  async exportJsonl(corpusPath: string, outputDir: string, normalized = false) {
    return this.call("export.jsonl", { corpus: corpusPath, output: outputDir, normalized });
  }

  async planPurge(projectDir: string) {
    return this.call("purge.plan", { project_dir: projectDir });
  }

  async confirmPurge(projectDir: string, mode: "trash" | "permanent", confirmToken: string) {
    return this.call("purge.confirm", { project_dir: projectDir, mode, confirm_token: confirmToken });
  }
}
