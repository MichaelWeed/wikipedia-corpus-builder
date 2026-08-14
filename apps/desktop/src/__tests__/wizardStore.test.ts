import { describe, it, expect } from "vitest";
import { useWizardStore } from "../store/wizardStore";

describe("useWizardStore", () => {
  it("initializes with step 1 and updates state", () => {
    const store = useWizardStore.getState();
    expect(store.step).toBe(1);

    store.setStep(2);
    expect(useWizardStore.getState().step).toBe(2);

    store.setProjectInfo("TestWiki", "/tmp/testwiki");
    expect(useWizardStore.getState().projectName).toBe("TestWiki");
    expect(useWizardStore.getState().projectDir).toBe("/tmp/testwiki");
  });

  it("accumulates log messages", () => {
    const store = useWizardStore.getState();
    store.clearLogs();
    expect(useWizardStore.getState().logs.length).toBe(0);

    store.addLog("Log entry 1");
    store.addLog("Log entry 2");
    expect(useWizardStore.getState().logs).toEqual(["Log entry 1", "Log entry 2"]);
  });

  it("tracks domainPath separately from domainLockPath", () => {
    const store = useWizardStore.getState();
    expect(store.domainPath).toBe("");
    expect(store.domainLockPath).toBe("");

    store.setDomainPath("/tmp/proj/domain.yaml");
    store.setDomainLockPath("/tmp/proj/domain.lock.json");

    const state = useWizardStore.getState();
    expect(state.domainPath).toBe("/tmp/proj/domain.yaml");
    expect(state.domainLockPath).toBe("/tmp/proj/domain.lock.json");
  });
});
