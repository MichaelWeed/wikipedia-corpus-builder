import { describe, it, expect, vi } from "vitest";
import { EngineClient, PROTOCOL_METHODS } from "../engine/client";

describe("EngineClient", () => {
  it("includes all expected protocol methods", () => {
    expect(PROTOCOL_METHODS).toContain("engine.hello");
    expect(PROTOCOL_METHODS).toContain("project.create");
    expect(PROTOCOL_METHODS).toContain("source.inspect");
    expect(PROTOCOL_METHODS).toContain("metadata.build");
    expect(PROTOCOL_METHODS).toContain("domain.compile");
    expect(PROTOCOL_METHODS).toContain("build.start");
    expect(PROTOCOL_METHODS).toContain("export.markdown");
    expect(PROTOCOL_METHODS).toContain("purge.confirm");
  });

  it("formats request correctly and handles response", async () => {
    const handler = vi.fn().mockResolvedValue({ protocol_version: 1, engine_version: "0.1.0" });
    const client = new EngineClient(handler);

    const res = await client.hello();
    expect(handler).toHaveBeenCalledWith("engine.hello", { client_version: "0.1.0" });
    expect(res).toEqual({ protocol_version: 1, engine_version: "0.1.0" });
  });

  it("passes correct arguments for startBuild", async () => {
    const handler = vi.fn().mockResolvedValue({ status: "BUILDING" });
    const client = new EngineClient(handler);

    await client.startBuild("/proj/lock.json", "/proj", "/out", true, false);
    expect(handler).toHaveBeenCalledWith("build.start", {
      domain: "/proj/lock.json",
      project_dir: "/proj",
      output: "/out",
      allow_low_disk: true,
      resume: false,
    });
  });

  it("passes correct arguments for createDomain", async () => {
    const handler = vi.fn().mockResolvedValue({ status: "created", domain_id: "my-wiki", domain_path: "/proj/domain.yaml" });
    const client = new EngineClient(handler);

    await client.createDomain("/proj", {
      name: "My Wiki",
      language: "en",
      intent: "Keep video games",
      roots: ["Video_games", "Category:Esports"],
      maxDepth: 6,
      facets: ["gaming"],
    });
    expect(handler).toHaveBeenCalledWith("domain.create", {
      project_dir: "/proj",
      name: "My Wiki",
      language: "en",
      intent: "Keep video games",
      roots: ["Video_games", "Category:Esports"],
      max_depth: 6,
      facets: ["gaming"],
    });
  });

  it("passes correct arguments for previewDomain and explainDomain", async () => {
    const handler = vi.fn().mockResolvedValue({});
    const client = new EngineClient(handler);

    await client.previewDomain("/proj/domain.yaml", "/proj");
    expect(handler).toHaveBeenCalledWith("domain.preview", {
      domain: "/proj/domain.yaml",
      project_dir: "/proj",
    });

    await client.explainDomain("/proj/domain.yaml", "/proj", "Some_Article");
    expect(handler).toHaveBeenCalledWith("domain.explain", {
      domain: "/proj/domain.yaml",
      project_dir: "/proj",
      page_title: "Some_Article",
    });
  });

  it("passes correct arguments for getBuildStatus and cancelBuild", async () => {
    const handler = vi.fn().mockResolvedValue({ status: "running" });
    const client = new EngineClient(handler);

    await client.getBuildStatus("job-123", "/proj");
    expect(handler).toHaveBeenCalledWith("build.status", { job_id: "job-123", project_dir: "/proj" });

    await client.cancelBuild("job-123");
    expect(handler).toHaveBeenCalledWith("build.cancel", { job_id: "job-123" });
  });
});
