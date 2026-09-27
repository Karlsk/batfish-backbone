import { describe, expect, it } from "vitest";
import { prepareConcern } from "./draft";

describe("business concern draft", () => {
  it("keeps all entered flows and advanced conditions in the submitted scope", () => {
    expect(
      prepareConcern("network", {
        name: "  订单系统  ",
        priority: "high",
        flows: [
          {
            start_location: "  r1  ",
            destination_ip: "10.0.0.9",
            source_ip: "10.0.0.1",
            protocol: "tcp",
            destination_port: 443,
          },
          { start_location: "r2", destination_ip: "10.0.0.10" },
        ],
      }),
    ).toEqual({
      network_id: "network",
      name: "订单系统",
      priority: "high",
      description: null,
      flows: [
        {
          start_location: "r1",
          destination_ip: "10.0.0.9",
          source_ip: "10.0.0.1",
          protocol: "tcp",
          destination_port: 443,
        },
        { start_location: "r2", destination_ip: "10.0.0.10" },
      ],
    });
  });

  it("rejects an invalid scope without silently dropping user input", () => {
    expect(() =>
      prepareConcern("network", {
        name: "订单",
        priority: "low",
        flows: [
          {
            start_location: "r1",
            destination_ip: "bad address",
            protocol: "icmp",
            destination_port: 443,
          },
        ],
      }),
    ).toThrow();
  });
});
