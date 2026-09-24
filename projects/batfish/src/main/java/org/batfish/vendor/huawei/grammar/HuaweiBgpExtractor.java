package org.batfish.vendor.huawei.grammar;

import java.util.Arrays;
import java.util.Set;
import org.batfish.common.Warnings;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;
import org.batfish.vendor.huawei.representation.HuaweiModel;
import org.batfish.vendor.huawei.representation.HuaweiStatement;
import org.batfish.vendor.huawei.representation.HuaweiStructureType;
import org.batfish.vendor.huawei.representation.HuaweiStructureUsage;

/** Transport attributes, groups and AF attributes have distinct ownership and lifetime. */
final class HuaweiBgpExtractor {
  private final HuaweiConfiguration _c;
  private final Warnings _w;

  HuaweiBgpExtractor(HuaweiConfiguration c, Warnings w) {
    _c = c;
    _w = w;
  }

  void extract(HuaweiStatement root, HuaweiModel.Bgp bgp) {
    HuaweiModel.BgpVrf base = bgp.vrfs.computeIfAbsent("default", k -> new HuaweiModel.BgpVrf());
    children(root, bgp, base, base, "default", "");
  }

  private void children(
      HuaweiStatement parent,
      HuaweiModel.Bgp bgp,
      HuaweiModel.BgpVrf base,
      HuaweiModel.BgpVrf scope,
      String vrf,
      String family) {
    for (HuaweiStatement s : parent.getChildren()) {
      try {
        statement(s, bgp, base, scope, vrf, family);
      } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
        unknown(s);
      }
    }
  }

  private void statement(
      HuaweiStatement s,
      HuaweiModel.Bgp bgp,
      HuaweiModel.BgpVrf base,
      HuaweiModel.BgpVrf scope,
      String vrf,
      String family) {
    String[] a = s.words();
    if (a[0].endsWith("-family")) {
      String targetVrf = a.length > 2 && a[1].equals("vpn-instance") ? a[2] : vrf;
      HuaweiModel.BgpVrf targetBase =
          bgp.vrfs.computeIfAbsent(targetVrf, k -> new HuaweiModel.BgpVrf());
      String af = a[0] + (a.length > 1 && !a[1].equals("vpn-instance") ? " " + a[1] : " unicast");
      HuaweiModel.BgpVrf target =
          targetBase.families.computeIfAbsent(af, k -> new HuaweiModel.BgpVrf());
      if (!targetVrf.equals("default")) {
        ref(HuaweiStructureType.VPN, targetVrf, HuaweiStructureUsage.BGP_VPN, s);
      }
      children(s, bgp, targetBase, target, targetVrf, af);
    } else if (a[0].equals("router-id")) {
      scope.routerId = Ip.parse(a[1]);
      if (family.isEmpty() && vrf.equals("default")) {
        bgp.routerId = scope.routerId;
      }
    } else if (a[0].equals("group")) {
      HuaweiModel.Peer group = scope.groups.computeIfAbsent(a[1], k -> new HuaweiModel.Peer());
      if (a.length > 2 && a[2].equals("internal")) {
        group.remoteAs = bgp.asn;
      }
      _c.defineSingleLineStructure(HuaweiStructureType.BGP_GROUP, vrf + ":" + a[1], s.getLine());
    } else if (a[0].equals("peer") || a[0].equals("undo") && a.length > 1 && a[1].equals("peer")) {
      boolean undo = a[0].equals("undo");
      if (undo) {
        a = Arrays.copyOfRange(a, 1, a.length);
      }
      if (Set.of(
                  "enable",
                  "ignore",
                  "shutdown",
                  "reflect-client",
                  "advertise-community",
                  "advertise-ext-community",
                  "substitute-as",
                  "next-hop-local")
              .contains(a[2])
          && a.length != 3) {
        unknown(s);
        return;
      }
      boolean group = base.groups.containsKey(a[1]) || scope.groups.containsKey(a[1]);
      HuaweiModel.Peer peer =
          (group ? scope.groups : scope.peers).computeIfAbsent(a[1], k -> new HuaweiModel.Peer());
      if (undo
          && !Set.of(
                  "enable",
                  "advertise-community",
                  "advertise-ext-community",
                  "reflect-client",
                  "ignore",
                  "shutdown")
              .contains(a[2])) {
        unknown(s);
        return;
      }
      switch (a[2]) {
        case "group" -> {
          peer.group = a[3];
          ref(HuaweiStructureType.BGP_GROUP, vrf + ":" + a[3], HuaweiStructureUsage.BGP_POLICY, s);
        }
        case "as-number" -> {
          long asn = Long.parseLong(a[3]);
          if (asn < 1 || asn > 0xFFFFFFFFL || a.length != 4) {
            throw new IllegalArgumentException();
          }
          peer.remoteAs = asn;
        }
        case "enable" -> peer.enabled = !undo;
        case "ignore", "shutdown" -> peer.shutdown = !undo;
        case "description" ->
            peer.description = String.join(" ", Arrays.copyOfRange(a, 3, a.length));
        case "connect-interface" -> {
          peer.sourceInterface = a[3];
          // A replacement connect-interface command replaces the complete source selection.
          peer.sourceIp = a.length > 4 ? Ip.tryParse(a[4]).orElse(null) : null;
          ref(HuaweiStructureType.INTERFACE, a[3], HuaweiStructureUsage.BGP_SOURCE, s);
        }
        case "ebgp-max-hop" -> peer.multihop = true;
        case "reflect-client" -> peer.reflectClient = !undo;
        case "advertise-community" -> peer.sendCommunity = !undo;
        case "advertise-ext-community" -> peer.sendExtendedCommunity = !undo;
        case "allow-as-loop" -> peer.allowAs = a.length > 3 ? Integer.valueOf(a[3]) : 1;
        case "substitute-as" -> peer.replaceAs = true;
        case "next-hop-local" -> peer.nextHopSelf = true;
        case "route-policy" -> {
          if (a.length != 5) {
            throw new IllegalArgumentException();
          }
          if (a[4].equals("import")) {
            peer.importPolicy = a[3];
          } else if (a[4].equals("export")) {
            peer.exportPolicy = a[3];
          } else {
            throw new IllegalArgumentException();
          }
          ref(HuaweiStructureType.ROUTE_POLICY, a[3], HuaweiStructureUsage.BGP_POLICY, s);
        }
        case "timer",
            "bfd",
            "route-limit",
            "advertise",
            "prefix-sid",
            "label-route-capability",
            "advertise-large-community",
            "preferred-value",
            "graceful-restart" ->
            peer.retained.add(s);
        // Authentication is recognized, but its value is never retained in diagnostics.
        case "password" -> {}
        default -> unknown(s);
      }
    } else if (a[0].equals("preference")) {
      if (a.length != 4) {
        throw new IllegalArgumentException();
      }
      scope.ebgpPreference = Integer.parseInt(a[1]);
      scope.ibgpPreference = Integer.parseInt(a[2]);
      scope.localPreference = Integer.parseInt(a[3]);
    } else if (a[0].equals("network")) {
      if (family.equals("ipv4-family unicast")) {
        int p = a.length > 2 && a[2].equals("mask") ? 3 : 2;
        int length = a[p].contains(".") ? Ip.parse(a[p]).numSubnetBits() : Integer.parseInt(a[p]);
        scope.networks.put(Prefix.create(Ip.parse(a[1]), length), option(a, "route-policy"));
        referencePolicy(a, s);
      } else {
        scope.retained.add(s);
        String locator = option(a, "locator");
        if (locator != null) {
          ref(HuaweiStructureType.LOCATOR, locator, HuaweiStructureUsage.SRV6_LOCATOR, s);
        }
      }
    } else if (a[0].equals("import-route")) {
      _c.getRetained().add(s);
      if (a.length > 1) {
        scope.redistribution.remove(a[1]);
      }
      HuaweiModel.Redistribution rule = HuaweiRedistributionExtractor.parse(a, true);
      if (rule.supported()) {
        scope.redistribution.put(a[1], rule);
      } else {
        _c.getUnsupportedRedistributions().add(new HuaweiModel.UnsupportedRedistribution("BGP", s));
      }
      referencePolicy(a, s);
    } else if (s.getText().equals("default-route imported")) {
      scope.importDefaultRoute = true;
    } else if (s.getText().equals("undo default-route imported")) {
      scope.importDefaultRoute = false;
    } else if (Set.of(
                "keep-all-routes",
                "graceful-restart",
                "private-4-byte-as",
                "segment-routing",
                "advertise",
                "dampening",
                "auto-frr",
                "nexthop",
                "route-select",
                "maximum",
                "aggregate",
                "timer",
                "bestroute",
                "undo")
            .contains(a[0])
        || s.getText().equals("policy vpn-target")) {
      if (a[0].equals("undo")
          && !Set.of("undo synchronization", "undo policy vpn-target", "undo router-id filter")
              .contains(s.getText())) {
        unknown(s);
      } else {
        scope.retained.add(s);
        String locator = option(a, "locator");
        if (locator != null) {
          ref(HuaweiStructureType.LOCATOR, locator, HuaweiStructureUsage.SRV6_LOCATOR, s);
        }
      }
    } else {
      unknown(s);
    }
  }

  private static String option(String[] a, String name) {
    for (int p = 0; p < a.length - 1; p++) {
      if (a[p].equals(name)) {
        return a[p + 1];
      }
    }
    return null;
  }

  private void referencePolicy(String[] a, HuaweiStatement s) {
    String policy = option(a, "route-policy");
    if (policy != null) {
      ref(HuaweiStructureType.ROUTE_POLICY, policy, HuaweiStructureUsage.REDISTRIBUTION_POLICY, s);
    }
  }

  private void ref(
      HuaweiStructureType type, String name, HuaweiStructureUsage usage, HuaweiStatement s) {
    _c.referenceStructure(type, name, usage, s.getLine());
  }

  private void unknown(HuaweiStatement s) {
    _c.setUnrecognized(true);
    _w.getParseWarnings()
        .add(
            new Warnings.ParseWarning(
                s.getLine(),
                s.words()[0],
                "huawei_bgp",
                "Unrecognized or malformed Huawei BGP command"));
  }
}
