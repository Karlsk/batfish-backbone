package org.batfish.vendor.huawei.grammar;

import java.util.HashSet;
import java.util.Set;
import org.batfish.vendor.huawei.representation.HuaweiModel;

/** Validates the entire import-route command before any IPv4 conversion is enabled. */
final class HuaweiRedistributionExtractor {
  static HuaweiModel.Redistribution parse(String[] a, boolean bgp) {
    if (a.length < 2
        || !(bgp
                ? Set.of("direct", "static", "isis", "ospf", "rip", "unr", "ospfv3", "ripng")
                : Set.of("direct", "static", "bgp", "isis", "ospf", "rip"))
            .contains(a[1])) {
      throw new IllegalArgumentException("Invalid redistribution protocol");
    }
    boolean supported = Set.of("direct", "static").contains(a[1]) || !bgp && a[1].equals("bgp");
    int p = 2;
    if (Set.of("isis", "ospf", "rip", "ospfv3", "ripng").contains(a[1])) {
      if (p < a.length && a[p].matches("[0-9]+")) {
        number(a[p++], 1, 65535);
      } else if (bgp) {
        throw new IllegalArgumentException("Missing source process");
      }
      supported = false; // VI redistribution cannot identify a source protocol process.
    }
    String policy = null;
    Long metric = null;
    Set<String> seen = new HashSet<>();
    while (p < a.length) {
      String key = a[p++];
      if (!seen.add(key)) {
        throw new IllegalArgumentException("Duplicate redistribution modifier");
      }
      switch (key) {
        case "med", "cost" -> {
          if (bgp != key.equals("med") || seen.contains("inherit-cost")) {
            throw new IllegalArgumentException("Invalid metric modifier");
          }
          metric = number(a[p++], 0, bgp ? 0xFFFFFFFFL : 4261412864L);
          // Wide-only costs require retained cost-style semantics not modeled in phase one.
          supported &= bgp || metric <= 63;
        }
        case "route-policy", "route-filter" -> {
          if (seen.contains(key.equals("route-policy") ? "route-filter" : "route-policy")) {
            throw new IllegalArgumentException("Conflicting policy modifiers");
          }
          String name = a[p++];
          if (key.equals("route-policy")) {
            policy = name;
          } else {
            supported = false;
          }
        }
        case "exclude" -> {
          if (!bgp || !a[1].equals("direct") || !a[p++].equals("vlink")) {
            throw new IllegalArgumentException("Invalid exclusion");
          }
          supported = false;
        }
        case "cost-type" -> {
          if (bgp
              || seen.contains("inherit-cost")
              || !Set.of("external", "internal").contains(a[p++])) {
            throw new IllegalArgumentException("Invalid cost type");
          }
          supported = false;
        }
        case "tag" -> {
          if (bgp) {
            throw new IllegalArgumentException("Invalid BGP modifier");
          }
          number(a[p++], 1, 0xFFFFFFFFL);
          supported = false;
        }
        case "level-1", "level-2", "level-1-2" -> {
          if (bgp || seen.stream().filter(k -> k.startsWith("level-")).count() > 1) {
            throw new IllegalArgumentException("Invalid redistribution level");
          }
          supported &= key.equals("level-2");
        }
        case "inherit-cost" -> {
          if (bgp || a[1].equals("static") || seen.contains("cost") || seen.contains("cost-type")) {
            throw new IllegalArgumentException("Invalid inherited cost");
          }
          supported = false;
        }
        default -> throw new IllegalArgumentException("Unknown redistribution modifier");
      }
    }
    return new HuaweiModel.Redistribution(policy, metric, supported);
  }

  private static long number(String text, long min, long max) {
    long value = Long.parseLong(text);
    if (!text.matches("[0-9]+") || value < min || value > max) {
      throw new IllegalArgumentException("Redistribution value out of range");
    }
    return value;
  }

  private HuaweiRedistributionExtractor() {}
}
