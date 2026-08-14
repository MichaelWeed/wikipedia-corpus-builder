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
});
