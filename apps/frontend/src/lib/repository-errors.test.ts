import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { describeError } from "@/lib/repository-errors";

describe("describeError", () => {
  it("maps github_rate_limited to a retryable message", () => {
    const friendly = describeError(new ApiError(429, "github_rate_limited", "rate limit"));
    expect(friendly.title).toContain("rate limit");
    expect(friendly.kind).toBe("retry");
  });

  it("maps github_token_invalid to a reconnect action", () => {
    const friendly = describeError(new ApiError(401, "github_token_invalid", "bad token"));
    expect(friendly.kind).toBe("reconnect");
  });

  it("maps github_not_connected to a reconnect action", () => {
    const friendly = describeError(new ApiError(401, "github_not_connected", "nope"));
    expect(friendly.kind).toBe("reconnect");
  });

  it("maps not_found to a fatal action", () => {
    const friendly = describeError(new ApiError(404, "not_found", "gone"));
    expect(friendly.kind).toBe("fatal");
    expect(friendly.title).toContain("not found");
  });

  it("maps a network failure to a retryable message", () => {
    const friendly = describeError(new ApiError(0, "network_error", "unreachable"));
    expect(friendly.kind).toBe("retry");
    expect(friendly.title).toContain("API");
  });

  it("falls back to a generic message for unknown codes", () => {
    const friendly = describeError(new ApiError(500, "wibble", "boom"));
    expect(friendly.title).toBe("Something went wrong");
    expect(friendly.message).toContain("boom");
    expect(friendly.kind).toBe("retry");
  });

  it("handles non-ApiError values without throwing", () => {
    expect(describeError("string error").kind).toBe("retry");
    expect(describeError(null).kind).toBe("retry");
  });
});
