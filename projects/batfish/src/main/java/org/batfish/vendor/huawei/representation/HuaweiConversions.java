package org.batfish.vendor.huawei.representation;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.ConfigurationFormat;
import org.batfish.datamodel.DeviceModel;
import org.batfish.datamodel.Interface;
import org.batfish.datamodel.InterfaceType;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.IsoAddress;
import org.batfish.datamodel.LineAction;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.PrefixRange;
import org.batfish.datamodel.PrefixSpace;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.StaticRoute;
import org.batfish.datamodel.SwitchportMode;
import org.batfish.datamodel.Vrf;
import org.batfish.datamodel.bgp.RouteDistinguisher;
import org.batfish.datamodel.isis.IsisInterfaceLevelSettings;
import org.batfish.datamodel.isis.IsisInterfaceMode;
import org.batfish.datamodel.isis.IsisInterfaceSettings;
import org.batfish.datamodel.isis.IsisLevelSettings;
import org.batfish.datamodel.isis.IsisProcess;
import org.batfish.datamodel.route.nh.NextHop;
import org.batfish.datamodel.route.nh.NextHopDiscard;
import org.batfish.datamodel.route.nh.NextHopInterface;
import org.batfish.datamodel.route.nh.NextHopIp;
import org.batfish.datamodel.route.nh.NextHopVrf;
import org.batfish.datamodel.routing_policy.RoutingPolicy;
import org.batfish.datamodel.routing_policy.expr.BooleanExpr;
import org.batfish.datamodel.routing_policy.expr.BooleanExprs;
import org.batfish.datamodel.routing_policy.expr.CallExpr;
import org.batfish.datamodel.routing_policy.expr.Conjunction;
import org.batfish.datamodel.routing_policy.expr.DestinationNetwork;
import org.batfish.datamodel.routing_policy.expr.ExplicitPrefixSet;
import org.batfish.datamodel.routing_policy.expr.LiteralLong;
import org.batfish.datamodel.routing_policy.expr.MatchPrefixSet;
import org.batfish.datamodel.routing_policy.expr.MatchProtocol;
import org.batfish.datamodel.routing_policy.expr.Not;
import org.batfish.datamodel.routing_policy.expr.WithEnvironmentExpr;
import org.batfish.datamodel.routing_policy.statement.If;
import org.batfish.datamodel.routing_policy.statement.SetMetric;
import org.batfish.datamodel.routing_policy.statement.Statement;
import org.batfish.datamodel.routing_policy.statement.Statements;

/** Converts only behavior expressible by the existing IPv4 VI model. */
public final class HuaweiConversions {
  public static Configuration convert(HuaweiConfiguration vc) {
    Configuration c = new Configuration(vc.getHostname(), ConfigurationFormat.HUAWEI_VRP);
    c.setDeviceModel(DeviceModel.HUAWEI_VRP_UNSPECIFIED);
    c.setDefaultCrossZoneAction(LineAction.PERMIT);
    c.setDefaultInboundAction(LineAction.PERMIT);
    c.setExportBgpFromBgpRib(false);
    c.getVrfs().put("default", new Vrf("default"));
    vc.getVpns()
        .forEach(
            (name, vpn) -> {
              Vrf vrf = new Vrf(name);
              HuaweiModel.Evpn af = vpn.families.get("ipv4");
              String rd = af != null && af.rd != null ? af.rd : vpn.rd;
              if (rd != null) {
                vrf.setRouteDistinguisher(parseRd(rd));
              }
              c.getVrfs().put(name, vrf);
            });
    if (vc.getDcnVpn() != null) {
      c.getVrfs().putIfAbsent(vc.getDcnVpn(), new Vrf(vc.getDcnVpn()));
    }
    interfaces(vc, c);
    staticRoutes(vc, c);
    HuaweiPolicyConversions.convert(vc, c);
    isis(vc, c);
    HuaweiBgpConversions.convert(vc, c);
    warnLimitations(vc);
    return c;
  }

  private static void interfaces(HuaweiConfiguration vc, Configuration c) {
    for (HuaweiModel.Interface i : vc.getInterfaces().values()) {
      Vrf vrf = c.getVrfs().get(i.vrf);
      if (vrf == null) {
        vc.getWarnings()
            .redFlagf(
                "Huawei interface %s references undefined VPN %s; interface disabled",
                i.name, i.vrf);
        vrf = c.getDefaultVrf();
      }
      Interface.Builder builder =
          Interface.builder()
              .setName(i.name)
              .setOwner(c)
              .setVrf(vrf)
              .setType(interfaceType(i.name))
              .setAdminUp(!i.shutdown && c.getVrfs().containsKey(i.vrf))
              .setDescription(i.description)
              .setMtu(i.mtu == null ? 1500 : i.mtu)
              .setSwitchport(i.bridge)
              .setEncapsulationVlan(i.vlan)
              .setChannelGroup(i.aggregate);
      if (i.name.startsWith("Vlanif")) {
        builder.setVlan(Integer.parseInt(i.name.substring("Vlanif".length())));
      }
      if (i.bridge) {
        builder
            .setSwitchportMode(i.trunk ? SwitchportMode.TRUNK : SwitchportMode.ACCESS)
            .setAccessVlan(i.accessVlan)
            .setNativeVlan(1)
            .setAllowedVlans(i.allowedVlans);
      }
      if (!i.addresses.isEmpty()) {
        builder.setAddresses(
            i.addresses.get(0),
            i.addresses
                .subList(1, i.addresses.size())
                .toArray(org.batfish.datamodel.InterfaceAddress[]::new));
      }
      if (i.name.contains(".")) {
        builder.setDependencies(
            List.of(
                new Interface.Dependency(
                    i.name.substring(0, i.name.indexOf('.')), Interface.DependencyType.BIND)));
      }
      builder.build();
    }
    for (HuaweiModel.Interface i : vc.getInterfaces().values()) {
      if (i.aggregate == null || !c.getAllInterfaces().containsKey(i.aggregate)) {
        continue;
      }
      Interface aggregate = c.getAllInterfaces().get(i.aggregate);
      Set<String> members = new TreeSet<>(aggregate.getChannelGroupMembers());
      members.add(i.name);
      aggregate.setChannelGroupMembers(members);
      List<Interface.Dependency> dependencies = new ArrayList<>(aggregate.getDependencies());
      dependencies.add(new Interface.Dependency(i.name, Interface.DependencyType.AGGREGATE));
      aggregate.setDependencies(dependencies);
    }
  }

  private static InterfaceType interfaceType(String name) {
    if (name.contains(".")) {
      return InterfaceType.LOGICAL;
    }
    if (name.startsWith("LoopBack")) {
      return InterfaceType.LOOPBACK;
    }
    if (name.startsWith("Eth-Trunk")) {
      return InterfaceType.AGGREGATED;
    }
    if (name.startsWith("Vlanif")) {
      return InterfaceType.VLAN;
    }
    if (name.startsWith("Tunnel") || name.startsWith("Nve")) {
      return InterfaceType.TUNNEL;
    }
    if (name.equalsIgnoreCase("NULL0")) {
      return InterfaceType.NULL;
    }
    return InterfaceType.PHYSICAL;
  }

  private static void staticRoutes(HuaweiConfiguration vc, Configuration c) {
    int unsupportedVrfNextHops = 0;
    for (HuaweiModel.StaticRoute r : vc.getStaticRoutes()) {
      Vrf vrf = c.getVrfs().get(r.vrf);
      if (vrf == null) {
        vc.getWarnings().redFlagf("Huawei static route references undefined VPN %s", r.vrf);
        continue;
      }
      NextHop nextHop;
      if (r.nextHopVrf != null) {
        if (r.nextHop != null) {
          unsupportedVrfNextHops++;
          continue;
        }
        nextHop = NextHopVrf.of(r.nextHopVrf);
      } else if (r.nextHopInterface != null) {
        nextHop =
            r.nextHopInterface.equalsIgnoreCase("NULL0")
                ? NextHopDiscard.instance()
                : r.nextHop == null
                    ? NextHopInterface.of(r.nextHopInterface)
                    : NextHopInterface.of(r.nextHopInterface, r.nextHop);
      } else {
        nextHop = NextHopIp.of(r.nextHop);
      }
      vrf.getStaticRoutes()
          .add(
              StaticRoute.builder()
                  .setNetwork(r.network)
                  .setNextHop(nextHop)
                  .setAdministrativeCost(r.preference)
                  .setTag(r.tag)
                  .build());
    }
    if (unsupportedVrfNextHops > 0) {
      vc.getWarnings()
          .redFlagf(
              "Huawei static: %d routes use a next-hop VPN/public with an explicit next-hop IP;"
                  + " retained, not converted",
              unsupportedVrfNextHops);
    }
  }

  private static void isis(HuaweiConfiguration vc, Configuration c) {
    Comparator<HuaweiModel.Isis> ranking =
        Comparator.comparingLong(
                (HuaweiModel.Isis p) ->
                    vc.getInterfaces().values().stream()
                        .filter(
                            i ->
                                i.vrf.equals("default")
                                    && i.isis != null
                                    && i.isis == p.id
                                    && !i.addresses.isEmpty())
                        .count())
            .thenComparingInt(p -> -p.id);
    HuaweiModel.Isis selected =
        vc.getIsisProcesses().values().stream()
            .filter(
                p ->
                    p.vrf.equals("default")
                        && (p.ipv4
                            || vc.getInterfaces().values().stream()
                                .anyMatch(i -> i.isis != null && i.isis == p.id)))
            .max(ranking)
            .orElse(null);
    if (selected == null) {
      if (!vc.getIsisProcesses().isEmpty()) {
        vc.getWarnings()
            .redFlagf(
                "Huawei ISIS: %d processes retained, not converted; no eligible default-VRF IPv4"
                    + " process",
                vc.getIsisProcesses().size());
      }
      return;
    }
    if (vc.getIsisProcesses().size() > 1) {
      vc.getWarnings()
          .redFlagf(
              "Huawei ISIS: selected process %d; other processes retained, not converted: %s",
              selected.id,
              vc.getIsisProcesses().keySet().stream().filter(id -> id != selected.id).toList());
    }
    if (selected.net == null) {
      vc.getWarnings().redFlag("Huawei ISIS selected process has no NET; not converted");
      return;
    }
    IsoAddress net = new IsoAddress(selected.net);
    boolean l1 = !selected.level.equals("level-2");
    boolean l2 = !selected.level.equals("level-1");
    String export = "~Huawei_ISIS_EXPORT~";
    List<Statement> exportStatements = new ArrayList<>();
    exportStatements.add(new SetMetric(new LiteralLong(0)));
    if ((l1 || !l2) && !selected.redistribution.isEmpty()) {
      // The existing dataplane initializes dual-level redistribution as EL1; a policy
      // can change the level but not that protocol. Do not fabricate an EL1/L2 hybrid.
      vc.getWarnings()
          .redFlag(
              "Huawei ISIS: redistribution requires a level-2-only process in this model; retained,"
                  + " not converted");
    } else {
      selected.redistribution.forEach(
          (protocol, rule) -> {
            WithEnvironmentExpr redistribution = new WithEnvironmentExpr();
            redistribution.setPreStatements(
                List.of(new SetMetric(new LiteralLong(rule.metric() == null ? 0 : rule.metric()))));
            redistribution.setExpr(call(c, rule.policy()));
            exportStatements.add(
                new If(
                    new Conjunction(List.of(protocol(protocol), notDefaultRoute(), redistribution)),
                    List.of(Statements.ExitAccept.toStaticStatement())));
          });
    }
    exportStatements.add(Statements.ExitReject.toStaticStatement());
    RoutingPolicy.builder().setOwner(c).setName(export).setStatements(exportStatements).build();
    IsisProcess.builder()
        .setVrf(c.getDefaultVrf())
        .setNetAddress(net)
        .setOverload(selected.overload)
        .setLevel1(l1 ? IsisLevelSettings.builder().build() : null)
        .setLevel2(l2 ? IsisLevelSettings.builder().build() : null)
        .setExportPolicy(export)
        .build();
    vc.getInterfaces().values().stream()
        .filter(i -> i.isis != null && i.isis == selected.id && i.vrf.equals("default"))
        .forEach(
            i -> {
              IsisInterfaceMode mode =
                  i.isisSilent || i.name.startsWith("LoopBack")
                      ? IsisInterfaceMode.PASSIVE
                      : IsisInterfaceMode.ACTIVE;
              IsisInterfaceSettings.Builder settings =
                  IsisInterfaceSettings.builder().setIsoAddress(net).setPointToPoint(i.isisP2p);
              if (l1 && !i.isisLevel.equals("level-2")) {
                settings.setLevel1(
                    IsisInterfaceLevelSettings.builder()
                        .setMode(mode)
                        .setCost(i.isisCostL1 == null ? i.isisCost : i.isisCostL1)
                        .build());
              }
              if (l2 && !i.isisLevel.equals("level-1")) {
                settings.setLevel2(
                    IsisInterfaceLevelSettings.builder()
                        .setMode(mode)
                        .setCost(i.isisCostL2 == null ? i.isisCost : i.isisCostL2)
                        .build());
              }
              Long bfdInterval =
                  i.bfdMinimumInterval != null ? i.bfdMinimumInterval : selected.bfdMinimumInterval;
              if ((i.isisBfd || selected.bfd) && bfdInterval != null) {
                settings.setBfdLivenessDetectionMinimumInterval(bfdInterval.intValue());
              }
              c.getAllInterfaces().get(i.name).setIsis(settings.build());
            });
  }

  static BooleanExpr protocol(String name) {
    return switch (name) {
      case "direct" -> new MatchProtocol(RoutingProtocol.CONNECTED);
      case "static" -> new MatchProtocol(RoutingProtocol.STATIC);
      case "bgp" -> new MatchProtocol(RoutingProtocol.BGP, RoutingProtocol.IBGP);
      default -> BooleanExprs.FALSE;
    };
  }

  static BooleanExpr notDefaultRoute() {
    return new Not(
        new MatchPrefixSet(
            DestinationNetwork.instance(),
            new ExplicitPrefixSet(new PrefixSpace(PrefixRange.fromPrefix(Prefix.ZERO)))));
  }

  static BooleanExpr call(Configuration c, String policy) {
    return policy == null
        ? BooleanExprs.TRUE
        : c.getRoutingPolicies().containsKey(policy) ? new CallExpr(policy) : BooleanExprs.FALSE;
  }

  private static void warnLimitations(HuaweiConfiguration vc) {
    for (String target : List.of("BGP", "ISIS")) {
      long count =
          vc.getUnsupportedRedistributions().stream()
              .filter(r -> r.target().equals(target))
              .count();
      if (count > 0) {
        vc.getWarnings()
            .redFlagf(
                "Huawei %s: %d redistribution commands have unsupported source protocols/processes"
                    + " or modifiers; retained, not converted",
                target.equals("BGP") ? "BGP operational limitations" : "ISIS", count);
      }
    }
    long v6Interfaces =
        vc.getInterfaces().values().stream().filter(i -> !i.ipv6Addresses.isEmpty()).count();
    long v6Peers =
        vc.getBgpProcesses().stream()
            .flatMap(b -> b.vrfs.values().stream())
            .flatMap(
                v ->
                    java.util.stream.Stream.concat(
                        java.util.stream.Stream.of(v), v.families.values().stream()))
            .flatMap(v -> v.peers.keySet().stream())
            .filter(p -> Ip.tryParse(p).isEmpty())
            .count();
    long unsupportedGuards =
        vc.getPolicies().values().stream()
            .flatMap(p -> p.nodes.values().stream())
            .filter(n -> n.matches.containsKey("rd") || n.matches.containsKey("ipv6-next-hop"))
            .count();
    if (v6Interfaces + v6Peers + vc.getIpv6StaticRoutes().size() > 0
        || vc.getIsisProcesses().values().stream().anyMatch(i -> i.ipv6)) {
      vc.getWarnings()
          .redFlagf(
              "Huawei IPv6 retained, not simulated: %d addressed interfaces, %d static routes, %d"
                  + " BGP peers; IPv6 ISIS/SR not converted",
              v6Interfaces, vc.getIpv6StaticRoutes().size(), v6Peers);
    }
    if (!vc.getEvpnInstances().isEmpty()
        || !vc.getEvpls().isEmpty()
        || !vc.getLocators().isEmpty()
        || !vc.getBridgeDomains().isEmpty()) {
      vc.getWarnings()
          .redFlagf(
              "Huawei EVPN/MPLS/SRv6 retained, not simulated: %d VPN instances, %d EVPN instances,"
                  + " %d EVPL groups, %d locators; no VNI or EVPN sessions fabricated",
              vc.getVpns().size(),
              vc.getEvpnInstances().size(),
              vc.getEvpls().size(),
              vc.getLocators().size());
    }
    if (unsupportedGuards > 0) {
      vc.getWarnings()
          .redFlagf(
              "Huawei route-policy: %d nodes have RD/IPv6 next-hop matches; those matches converted"
                  + " to FALSE",
              unsupportedGuards);
    }
    long disabledNodes =
        vc.getPolicies().values().stream()
            .flatMap(p -> p.nodes.values().stream())
            .filter(n -> n.unsupported)
            .count();
    if (disabledNodes > 0) {
      vc.getWarnings()
          .redFlagf(
              "Huawei route-policy: %d nodes disabled due to unsupported whole-match or invalid"
                  + " commands",
              disabledNodes);
    }
    if (!vc.getOspfProcesses().isEmpty()) {
      vc.getWarnings()
          .redFlagf(
              "Huawei OSPF retained, not simulated: %d processes", vc.getOspfProcesses().size());
    }
    long extraInstances =
        vc.getBgpProcesses().stream().filter(b -> !b.instance.equals("default")).count();
    if (extraInstances > 0) {
      vc.getWarnings()
          .redFlagf("Huawei additional BGP instances retained, not converted: %d", extraInstances);
    }
    List<HuaweiModel.BgpVrf> bgpScopes =
        vc.getBgpProcesses().stream()
            .flatMap(b -> b.vrfs.values().stream())
            .flatMap(
                v ->
                    java.util.stream.Stream.concat(
                        java.util.stream.Stream.of(v), v.families.values().stream()))
            .toList();
    long operationalPeers =
        bgpScopes.stream()
            .flatMap(
                v ->
                    java.util.stream.Stream.concat(
                        v.peers.values().stream(), v.groups.values().stream()))
            .filter(p -> !p.retained.isEmpty() || p.allowAs != null && p.allowAs > 0)
            .count();
    long retainedOptions = bgpScopes.stream().mapToLong(v -> v.retained.size()).sum();
    long unsupportedFamilies =
        vc.getBgpProcesses().stream()
            .flatMap(b -> b.vrfs.values().stream())
            .flatMap(v -> v.families.keySet().stream())
            .filter(af -> !af.equals("ipv4-family unicast"))
            .count();
    if (operationalPeers > 0 || retainedOptions > 0 || unsupportedFamilies > 0) {
      vc.getWarnings()
          .redFlagf(
              "Huawei BGP operational limitations on %d peer/group definitions, %d scope options,"
                  + " %d unsupported address families: timers/BFD/route-limit retained;"
                  + " allow-as-loop count represented as boolean",
              operationalPeers, retainedOptions, unsupportedFamilies);
    }
  }

  private static RouteDistinguisher parseRd(String text) {
    String normalized = text;
    String[] halves = text.split(":");
    if (halves[0].chars().filter(c -> c == '.').count() == 1) {
      String[] asn = halves[0].split("\\.");
      normalized = ((Long.parseLong(asn[0]) << 16) | Long.parseLong(asn[1])) + ":" + halves[1];
    }
    return RouteDistinguisher.parse(normalized);
  }

  private HuaweiConversions() {}
}
