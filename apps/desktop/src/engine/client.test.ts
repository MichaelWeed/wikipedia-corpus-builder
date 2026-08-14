import { expect, test } from "vitest";
import { EngineClient, PROTOCOL_METHODS } from "./client";

test("EngineClient method calls match protocol surface", async () => {
  const calls: string[] = [];
  const client = new EngineClient(async (method) => {
    calls.push(method);
    return { ok: true };
  });

  await client.hello();
  await client.inspectSource("/path/to/source");
  await client.compileDomain("domain.yaml", "/project");

  expect(calls).toContain("engine.hello");
  expect(calls).toContain("source.inspect");
  expect(calls).toContain("domain.compile");
  expect(PROTOCOL_METHODS.length).toBeGreaterThanOrEqual(10);
});
