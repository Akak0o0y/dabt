import { describe, expect, it } from "vitest";
import type { TrpcContext } from "./_core/context";
import { appRouter } from "./routers";

const context: TrpcContext = {
  user: null,
  req: {} as TrpcContext["req"],
  res: {} as TrpcContext["res"],
};

describe("dabt.buildInfo", () => {
  it("publicly exposes the documentation checkpoint without exposing policy payloads", async () => {
    const result = await appRouter.createCaller(context).dabt.buildInfo();

    expect(result).toMatchObject({
      documentationCheckpoint: "9b13792a",
      policyMapVersion: "0.1.0-research-grounded",
      releaseScope: "documentation-and-stability-wrap-up",
    });
    expect(result).not.toHaveProperty("document");
    expect(result).not.toHaveProperty("payload");
  });
});
