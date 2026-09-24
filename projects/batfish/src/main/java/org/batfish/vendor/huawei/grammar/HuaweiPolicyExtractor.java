package org.batfish.vendor.huawei.grammar;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.batfish.common.Warnings;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.vendor.huawei.representation.HuaweiCommunity;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;
import org.batfish.vendor.huawei.representation.HuaweiModel;
import org.batfish.vendor.huawei.representation.HuaweiStatement;
import org.batfish.vendor.huawei.representation.HuaweiStructureType;
import org.batfish.vendor.huawei.representation.HuaweiStructureUsage;

/** Huawei route-policy and named filter extraction. */
final class HuaweiPolicyExtractor {
  private final HuaweiConfiguration _c;
  private final Warnings _w;

  HuaweiPolicyExtractor(HuaweiConfiguration c, Warnings w) {
    _c = c;
    _w = w;
  }

  void prefixList(HuaweiStatement s) {
    String[] a = s.words();
    int p = 3;
    Map<Integer, HuaweiModel.PrefixEntry> list =
        _c.getPrefixLists().computeIfAbsent(a[2], k -> new TreeMap<>());
    int index = list.keySet().stream().mapToInt(Integer::intValue).max().orElse(0) + 10;
    if (a[p].equals("index")) {
      index = Integer.parseInt(a[++p]);
      p++;
    }
    require(Set.of("permit", "deny").contains(a[p]));
    boolean permit = a[p++].equals("permit");
    Prefix prefix = Prefix.create(Ip.parse(a[p++]), Integer.parseInt(a[p++]));
    int min = prefix.getPrefixLength();
    int max = min;
    while (p < a.length) {
      switch (a[p++]) {
        case "greater-equal" -> {
          min = Integer.parseInt(a[p++]);
          max = 32;
        }
        case "less-equal" -> max = Integer.parseInt(a[p++]);
        default -> throw new IllegalArgumentException("prefix-list option");
      }
    }
    require(min >= prefix.getPrefixLength() && max >= min && max <= 32);
    list.put(index, new HuaweiModel.PrefixEntry(permit, prefix, min, max));
    define(HuaweiStructureType.PREFIX_LIST, a[2], s);
  }

  void communityList(HuaweiStatement s) {
    String[] a = s.words();
    boolean ext = a[1].equals("extcommunity-filter");
    int p = 2;
    boolean regex = a[p].equals("advanced");
    if (a[p].equals("basic") || regex) {
      p++;
    }
    String name = a[p++];
    regex |= !ext && name.matches("1[0-9]{2}");
    Map<Integer, HuaweiModel.CommunityEntry> entries =
        (ext ? _c.getExtcommunities() : _c.getCommunities())
            .computeIfAbsent(name, k -> new TreeMap<>());
    define(
        ext ? HuaweiStructureType.EXTCOMMUNITY_LIST : HuaweiStructureType.COMMUNITY_LIST, name, s);
    try {
      int index = entries.keySet().stream().mapToInt(Integer::intValue).max().orElse(0) + 10;
      if (a[p].equals("index")) {
        index = Integer.parseInt(a[p + 1]);
        p += 2;
      }
      require(Set.of("permit", "deny").contains(a[p]));
      boolean permit = a[p++].equals("permit");
      require(p < a.length);
      List<String> values = List.of(Arrays.copyOfRange(a, p, a.length));
      if (!regex) {
        if (ext) {
          HuaweiCommunity.parseExtendedValues(values);
        } else {
          values.forEach(HuaweiCommunity::parse);
        }
      }
      entries.put(index, new HuaweiModel.CommunityEntry(permit, regex, values));
    } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
      // Dropping only a malformed deny could incorrectly admit a later permit.
      (ext ? _c.getInvalidExtcommunities() : _c.getInvalidCommunities()).add(name);
      unknown(s, "Malformed community filter; entire list disabled");
    }
  }

  void node(HuaweiStatement s, HuaweiModel.PolicyNode node) {
    String t = s.getText();
    String[] a = s.words();
    if (a[0].equals("if-match")) {
      HuaweiStructureType type;
      String key;
      int p;
      if (t.startsWith("if-match ip-prefix ")) {
        type = HuaweiStructureType.PREFIX_LIST;
        key = "prefix";
        p = 2;
      } else if (t.startsWith("if-match ipv6 next-hop prefix-list ")) {
        type = HuaweiStructureType.IPV6_PREFIX_LIST;
        key = "ipv6-next-hop";
        p = 4;
      } else if (a[1].equals("community-filter")) {
        type = HuaweiStructureType.COMMUNITY_LIST;
        key = "community";
        p = a[2].equals("name") ? 3 : 2;
      } else if (a[1].equals("extcommunity-filter")) {
        type = HuaweiStructureType.EXTCOMMUNITY_LIST;
        key = "extcommunity";
        p = 2;
      } else if (a[1].equals("rd-filter")) {
        type = HuaweiStructureType.RD_LIST;
        key = "rd";
        p = 2;
      } else {
        node.unsupported = true;
        unknown(s, "Unrecognized route-policy match");
        return;
      }
      require(p < a.length);
      List<String> names = node.matches.computeIfAbsent(key, k -> new ArrayList<>());
      for (; p < a.length; p++) {
        if (key.equals("community") && a[p].equals("name")) {
          continue;
        }
        if (a[p].equals("whole-match")) {
          node.unsupported = true;
          _c.getRetained().add(s);
          continue;
        }
        names.add(a[p]);
        ref(type, a[p], HuaweiStructureUsage.POLICY_MATCH, s);
      }
    } else if (starts(
        t,
        "apply community",
        "apply extcommunity color",
        "apply cost",
        "apply local-preference",
        "apply ip-address next-hop")) {
      try {
        validateAction(a);
      } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
        node.unsupported = true;
        unknown(s, "Malformed route-policy action; node disabled");
        return;
      }
      node.actions.add(s);
    } else {
      node.unsupported = true;
      unknown(s, "Unrecognized route-policy command");
    }
  }

  private static void validateAction(String[] a) {
    if (a[1].equals("cost") || a[1].equals("local-preference")) {
      if (a.length != 3 || !a[2].matches("[0-9]+") || Long.parseLong(a[2]) > 0xFFFFFFFFL) {
        throw new IllegalArgumentException("invalid numeric action");
      }
    } else if (a[1].equals("ip-address")) {
      if (a.length != 4 || !a[2].equals("next-hop")) {
        throw new IllegalArgumentException("next hop");
      }
      Ip.parse(a[3]);
    } else if (a[1].equals("community")) {
      int end = a.length - (a[a.length - 1].equals("additive") ? 1 : 0);
      if (end <= 2) {
        throw new IllegalArgumentException("missing community");
      }
      for (int p = 2; p < end; p++) {
        HuaweiCommunity.parse(a[p]);
      }
    } else if (a[1].equals("extcommunity")) {
      int end = a.length - (a[a.length - 1].equals("additive") ? 1 : 0);
      if (end <= 3) {
        throw new IllegalArgumentException("missing color");
      }
      for (int p = 3; p < end; p++) {
        String[] color = a[p].split(":");
        if (color.length > 2 || Long.parseLong(color[color.length - 1]) > 0xFFFFFFFFL) {
          throw new IllegalArgumentException("invalid color");
        }
        if (color.length == 2 && Long.parseLong(color[0], 16) > 0xFFFF) {
          throw new IllegalArgumentException("invalid color flags");
        }
      }
    }
  }

  private static boolean starts(String text, String... prefixes) {
    return Arrays.stream(prefixes).anyMatch(p -> text.equals(p) || text.startsWith(p + " "));
  }

  private static void require(boolean valid) {
    if (!valid) {
      throw new IllegalArgumentException("Invalid Huawei VRP command arguments");
    }
  }

  private static int range(String value, int min, int max) {
    int number = Integer.parseInt(value);
    require(number >= min && number <= max);
    return number;
  }

  private void define(HuaweiStructureType type, String name, HuaweiStatement s) {
    _c.defineSingleLineStructure(type, name, s.getLine());
  }

  private void ref(
      HuaweiStructureType type, String name, HuaweiStructureUsage usage, HuaweiStatement s) {
    _c.referenceStructure(type, name, usage, s.getLine());
  }

  private void unknown(HuaweiStatement s, String reason) {
    _c.setUnrecognized(true);
    // Do not copy configuration values (which may be credentials) into diagnostics.
    _w.getParseWarnings()
        .add(new Warnings.ParseWarning(s.getLine(), s.words()[0], "huawei", reason));
  }
}
