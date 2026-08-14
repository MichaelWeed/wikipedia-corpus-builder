export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params: Record<string, any>;
}

export interface JsonRpcResponse<T = any> {
  jsonrpc: "2.0";
  id: number;
  result?: T;
  error?: {
    code: number;
    message: str;
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
  "source.inspect",
  "metadata.build",
  "metadata.search",
  "model.detect",
  "model.add",
  "model.list",
  "model.test",
  "domain.compile",
  "build.start",
  "corpus.validate",
  "export.markdown",
  "export.jsonl",
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

  async inspectSource(sourcePath: string) {
    return this.call("source.inspect", { source: sourcePath });
  }

  async buildMetadata(sourcePath: string, projectDir: string) {
    return this.call("metadata.build", { source: sourcePath, project_dir: projectDir });
  }

  async compileDomain(domainPath: string, projectDir: string) {
    return this.call("domain.compile", { domain: domainPath, project_dir: projectDir });
  }

  async startBuild(domainPath: string, projectDir: string, outputDir: string, allowLowDisk = false, resume = false) {
    return this.call("build.start", {
      domain: domainPath,
      project_dir: projectDir,
      output: outputDir,
      allow_low_disk: allowLowDisk,
      resume: resume,
    });
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
}
