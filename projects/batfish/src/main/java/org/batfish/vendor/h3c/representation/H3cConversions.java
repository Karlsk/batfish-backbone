package org.batfish.vendor.h3c.representation;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.batfish.datamodel.BgpActivePeerConfig;
import org.batfish.datamodel.BgpProcess;
import org.batfish.datamodel.BgpTieBreaker;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.ConfigurationFormat;
import org.batfish.datamodel.DeviceModel;
import org.batfish.datamodel.Interface;
import org.batfish.datamodel.InterfaceType;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.IsoAddress;
import org.batfish.datamodel.LineAction;
import org.batfish.datamodel.LongSpace;
import org.batfish.datamodel.OriginType;
import org.batfish.datamodel.PrefixRange;
import org.batfish.datamodel.PrefixSpace;
import org.batfish.datamodel.RouteFilterLine;
import org.batfish.datamodel.RouteFilterList;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.StaticRoute;
import org.batfish.datamodel.SubRange;
import org.batfish.datamodel.SwitchportMode;
import org.batfish.datamodel.Vrf;
import org.batfish.datamodel.bgp.AddressFamilyCapabilities;
import org.batfish.datamodel.bgp.Ipv4UnicastAddressFamily;
import org.batfish.datamodel.bgp.LocalOriginationTypeTieBreaker;
import org.batfish.datamodel.bgp.NextHopIpTieBreaker;
import org.batfish.datamodel.bgp.RouteDistinguisher;
import org.batfish.datamodel.bgp.community.Community;
import org.batfish.datamodel.bgp.community.ExtendedCommunity;
import org.batfish.datamodel.bgp.community.StandardCommunity;
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
import org.batfish.datamodel.routing_policy.communities.AllStandardCommunities;
import org.batfish.datamodel.routing_policy.communities.CommunityIs;
import org.batfish.datamodel.routing_policy.communities.CommunityMatchAny;
import org.batfish.datamodel.routing_policy.communities.CommunityMatchExpr;
import org.batfish.datamodel.routing_policy.communities.CommunitySet;
import org.batfish.datamodel.routing_policy.communities.CommunitySetAcl;
import org.batfish.datamodel.routing_policy.communities.CommunitySetAclLine;
import org.batfish.datamodel.routing_policy.communities.CommunitySetDifference;
import org.batfish.datamodel.routing_policy.communities.CommunitySetExpr;
import org.batfish.datamodel.routing_policy.communities.CommunitySetUnion;
import org.batfish.datamodel.routing_policy.communities.HasCommunity;
import org.batfish.datamodel.routing_policy.communities.InputCommunities;
import org.batfish.datamodel.routing_policy.communities.LiteralCommunitySet;
import org.batfish.datamodel.routing_policy.communities.MatchCommunities;
import org.batfish.datamodel.routing_policy.communities.SetCommunities;
import org.batfish.datamodel.routing_policy.expr.BooleanExpr;
import org.batfish.datamodel.routing_policy.expr.BooleanExprs;
import org.batfish.datamodel.routing_policy.expr.CallExpr;
import org.batfish.datamodel.routing_policy.expr.Conjunction;
import org.batfish.datamodel.routing_policy.expr.DestinationNetwork;
import org.batfish.datamodel.routing_policy.expr.Disjunction;
import org.batfish.datamodel.routing_policy.expr.ExplicitPrefixSet;
import org.batfish.datamodel.routing_policy.expr.IpNextHop;
import org.batfish.datamodel.routing_policy.expr.LiteralLong;
import org.batfish.datamodel.routing_policy.expr.LiteralOrigin;
import org.batfish.datamodel.routing_policy.expr.MatchPrefixSet;
import org.batfish.datamodel.routing_policy.expr.MatchProtocol;
import org.batfish.datamodel.routing_policy.expr.NamedPrefixSet;
import org.batfish.datamodel.routing_policy.expr.SelfNextHop;
import org.batfish.datamodel.routing_policy.expr.WithEnvironmentExpr;
import org.batfish.datamodel.routing_policy.statement.If;
import org.batfish.datamodel.routing_policy.statement.ReplaceAsesInAsSequence;
import org.batfish.datamodel.routing_policy.statement.SetLocalPreference;
import org.batfish.datamodel.routing_policy.statement.SetMetric;
import org.batfish.datamodel.routing_policy.statement.SetNextHop;
import org.batfish.datamodel.routing_policy.statement.SetOrigin;
import org.batfish.datamodel.routing_policy.statement.Statement;
import org.batfish.datamodel.routing_policy.statement.Statements;

/** Converts only behavior expressible by the existing IPv4 VI model. */
public final class H3cConversions {
  public static Configuration convert(H3cConfiguration vc) {
    Configuration c = new Configuration(vc.getHostname(), ConfigurationFormat.H3C_COMWARE);
    c.setDeviceModel(DeviceModel.H3C_COMWARE_UNSPECIFIED);
    c.setDefaultCrossZoneAction(LineAction.PERMIT);
    c.setDefaultInboundAction(LineAction.PERMIT);
    c.setExportBgpFromBgpRib(false);
    c.getVrfs().put("default", new Vrf("default"));
    vc.getVpns()
        .forEach(
            (name, vpn) -> {
              Vrf vrf = new Vrf(name);
              H3cModel.Evpn af = vpn.families.get("ipv4");
              String rd = af != null && af.rd != null ? af.rd : vpn.rd;
              if (rd != null) {
                vrf.setRouteDistinguisher(RouteDistinguisher.parse(rd));
              }
              c.getVrfs().put(name, vrf);
            });
    interfaces(vc, c);
    staticRoutes(vc, c);
    policies(vc, c);
    isis(vc, c);
    bgp(vc, c);
    warnLimitations(vc);
    return c;
  }

  private static void interfaces(H3cConfiguration vc, Configuration c) {
    for (H3cModel.Interface i : vc.getInterfaces().values()) {
      Vrf vrf = c.getVrfs().get(i.vrf);
      if (vrf == null) {
        vc.getWarnings()
            .redFlagf(
                "H3C interface %s references undefined VPN %s; interface disabled", i.name, i.vrf);
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
      if (i.name.startsWith("Vlan-interface")) {
        builder.setVlan(Integer.parseInt(i.name.substring("Vlan-interface".length())));
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
    for (H3cModel.Interface i : vc.getInterfaces().values()) {
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
    if (name.startsWith("Route-Aggregation") || name.startsWith("Bridge-Aggregation")) {
      return InterfaceType.AGGREGATED;
    }
    if (name.startsWith("Vlan-interface")) {
      return InterfaceType.VLAN;
    }
    if (name.startsWith("Tunnel")) {
      return InterfaceType.TUNNEL;
    }
    if (name.equalsIgnoreCase("NULL0")) {
      return InterfaceType.NULL;
    }
    return InterfaceType.PHYSICAL;
  }

  private static void staticRoutes(H3cConfiguration vc, Configuration c) {
    for (H3cModel.StaticRoute r : vc.getStaticRoutes()) {
      Vrf vrf = c.getVrfs().get(r.vrf);
      if (vrf == null) {
        vc.getWarnings().redFlagf("H3C static route references undefined VPN %s", r.vrf);
        continue;
      }
      NextHop nextHop;
      if (r.nextHopVrf != null) {
        if (r.nextHop != null) {
          vc.getWarnings()
              .redFlag(
                  "H3C static next-hop VPN with an explicit next-hop IP is retained but not"
                      + " converted");
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
  }

  private static void policies(H3cConfiguration vc, Configuration c) {
    vc.getPrefixLists()
        .forEach(
            (name, entries) ->
                c.getRouteFilterLists()
                    .put(
                        name,
                        new RouteFilterList(
                            name,
                            entries.values().stream()
                                .map(
                                    e ->
                                        new RouteFilterLine(
                                            e.permit() ? LineAction.PERMIT : LineAction.DENY,
                                            e.prefix(),
                                            new SubRange(e.min(), e.max())))
                                .toList())));
    vc.getPolicies()
        .forEach(
            (name, policy) -> {
              List<Statement> statements = new ArrayList<>();
              for (H3cModel.PolicyNode node : policy.nodes.values()) {
                List<BooleanExpr> conjuncts = new ArrayList<>();
                if (node.unsupported) {
                  conjuncts.add(BooleanExprs.FALSE);
                }
                node.matches.forEach(
                    (kind, names) -> {
                      List<BooleanExpr> disjuncts =
                          names.stream().map(n -> match(vc, c, kind, n)).toList();
                      conjuncts.add(new Disjunction(disjuncts));
                    });
                List<Statement> onMatch = new ArrayList<>();
                if (node.permit) {
                  for (H3cStatement action : node.actions) {
                    onMatch.add(action(action));
                  }
                }
                onMatch.add(terminal(node.permit));
                statements.add(new If(new Conjunction(conjuncts), onMatch));
              }
              statements.add(terminal(false));
              RoutingPolicy.builder().setOwner(c).setName(name).setStatements(statements).build();
            });
  }

  private static BooleanExpr match(H3cConfiguration vc, Configuration c, String kind, String name) {
    return switch (kind) {
      case "prefix" ->
          c.getRouteFilterLists().containsKey(name)
              ? new MatchPrefixSet(DestinationNetwork.instance(), new NamedPrefixSet(name))
              : BooleanExprs.TRUE;
      case "community", "extcommunity" -> communityMatch(vc, kind.equals("extcommunity"), name);
      // Existing VI routes have neither IPv6 next-hop nor a route distinguisher to match.
      default -> BooleanExprs.FALSE;
    };
  }

  private static BooleanExpr communityMatch(H3cConfiguration vc, boolean ext, String name) {
    Map<Integer, H3cModel.CommunityEntry> entries =
        (ext ? vc.getExtcommunities() : vc.getCommunities()).get(name);
    if (entries == null) {
      return BooleanExprs.TRUE;
    }
    List<CommunitySetAclLine> lines = new ArrayList<>();
    for (H3cModel.CommunityEntry entry : entries.values()) {
      if (entry.regex()) {
        vc.getWarnings()
            .redFlagf("H3C advanced community list %s is not converted; match disabled", name);
        return BooleanExprs.FALSE;
      }
      List<CommunityMatchExpr> values = new ArrayList<>();
      String type = "rt";
      for (String value : entry.values()) {
        if (ext && Set.of("rt", "soo", "color").contains(value)) {
          type = value;
          continue;
        }
        Community community;
        if (!ext) {
          community = StandardCommunity.parse(value);
        } else if (type.equals("color")) {
          String[] color = value.split(":");
          long encoded =
              color.length == 1
                  ? Long.parseLong(color[0])
                  : (Long.parseLong(color[0], 16) << 32) | Long.parseLong(color[1]);
          community = ExtendedCommunity.opaque(true, 11, encoded);
        } else {
          community = ExtendedCommunity.parse((type.equals("soo") ? "origin:" : "target:") + value);
        }
        values.add(new CommunityIs(community));
      }
      lines.add(
          new CommunitySetAclLine(
              entry.permit() ? LineAction.PERMIT : LineAction.DENY,
              new HasCommunity(new CommunityMatchAny(values))));
    }
    return new MatchCommunities(InputCommunities.instance(), new CommunitySetAcl(lines));
  }

  private static Statement action(H3cStatement s) {
    String[] a = s.words();
    return switch (a[1]) {
      case "cost" -> new SetMetric(new LiteralLong(Long.parseLong(a[2])));
      case "local-preference" -> new SetLocalPreference(new LiteralLong(Long.parseLong(a[2])));
      case "ip-address" -> new SetNextHop(new IpNextHop(List.of(Ip.parse(a[3]))));
      case "community", "extcommunity" -> {
        boolean ext = a[1].equals("extcommunity");
        boolean additive = a[a.length - 1].equals("additive");
        List<Community> communities = new ArrayList<>();
        for (int p = ext ? 3 : 2; p < a.length - (additive ? 1 : 0); p++) {
          if (ext) {
            String[] color = a[p].split(":");
            long value =
                color.length == 1
                    ? Long.parseLong(color[0])
                    : (Long.parseLong(color[0], 16) << 32) | Long.parseLong(color[1]);
            communities.add(ExtendedCommunity.opaque(true, 0x0B, value));
          } else {
            communities.add(StandardCommunity.parse(a[p]));
          }
        }
        CommunitySetExpr original = InputCommunities.instance();
        if (!additive && !ext) {
          original = new CommunitySetDifference(original, AllStandardCommunities.instance());
        }
        // Non-additive color replaces color communities only, preserving RT and standard
        // communities.
        if (!additive && ext) {
          original =
              new CommunitySetDifference(
                  original,
                  org.batfish.datamodel.routing_policy.communities.OpaqueExtendedCommunities.of(
                      true, 0x0B));
        }
        yield new SetCommunities(
            CommunitySetUnion.of(original, new LiteralCommunitySet(CommunitySet.of(communities))));
      }
      default -> throw new IllegalArgumentException("Unexpected extracted policy action");
    };
  }

  private static Statement terminal(boolean permit) {
    return new If(
        BooleanExprs.CALL_EXPR_CONTEXT,
        List.of((permit ? Statements.ReturnTrue : Statements.ReturnFalse).toStaticStatement()),
        List.of((permit ? Statements.ExitAccept : Statements.ExitReject).toStaticStatement()));
  }

  private static void isis(H3cConfiguration vc, Configuration c) {
    Comparator<H3cModel.Isis> ranking =
        Comparator.comparingLong(
                (H3cModel.Isis p) ->
                    vc.getInterfaces().values().stream()
                        .filter(
                            i ->
                                i.vrf.equals("default")
                                    && i.isis != null
                                    && i.isis == p.id
                                    && !i.addresses.isEmpty())
                        .count())
            .thenComparingInt(p -> -p.id);
    H3cModel.Isis selected =
        vc.getIsisProcesses().values().stream()
            .filter(
                p ->
                    p.ipv4
                        || vc.getInterfaces().values().stream()
                            .anyMatch(i -> i.isis != null && i.isis == p.id))
            .max(ranking)
            .orElse(null);
    if (selected == null) {
      return;
    }
    if (vc.getIsisProcesses().size() > 1) {
      vc.getWarnings()
          .redFlagf(
              "H3C ISIS: selected process %d; other processes retained, not converted: %s",
              selected.id,
              vc.getIsisProcesses().keySet().stream().filter(id -> id != selected.id).toList());
    }
    if (selected.net == null) {
      vc.getWarnings().redFlag("H3C ISIS selected process has no NET; not converted");
      return;
    }
    IsoAddress net = new IsoAddress(selected.net);
    boolean l1 = !selected.level.equals("level-2");
    boolean l2 = !selected.level.equals("level-1");
    String export = "~H3C_ISIS_EXPORT~";
    List<Statement> exportStatements = new ArrayList<>();
    exportStatements.add(new SetMetric(new LiteralLong(0)));
    selected.redistribution.forEach(
        (protocol, policy) ->
            exportStatements.add(
                new If(
                    new Conjunction(List.of(protocol(protocol), call(c, policy))),
                    List.of(Statements.ExitAccept.toStaticStatement()))));
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
              if (i.isisBfd && i.bfdMinimumInterval != null) {
                settings.setBfdLivenessDetectionMinimumInterval(i.bfdMinimumInterval.intValue());
              }
              c.getAllInterfaces().get(i.name).setIsis(settings.build());
            });
  }

  private static BooleanExpr protocol(String name) {
    return switch (name) {
      case "direct" -> new MatchProtocol(RoutingProtocol.CONNECTED);
      case "static" -> new MatchProtocol(RoutingProtocol.STATIC);
      case "bgp" -> new MatchProtocol(RoutingProtocol.BGP, RoutingProtocol.IBGP);
      default -> BooleanExprs.FALSE;
    };
  }

  private static BooleanExpr call(Configuration c, String policy) {
    return policy == null
        ? BooleanExprs.TRUE
        : c.getRoutingPolicies().containsKey(policy) ? new CallExpr(policy) : BooleanExprs.FALSE;
  }

  private static void bgp(H3cConfiguration vc, Configuration c) {
    for (H3cModel.Bgp bgp : vc.getBgpProcesses()) {
      if (!bgp.instance.equals("default")) {
        continue;
      }
      for (Map.Entry<String, H3cModel.BgpVrf> entry : bgp.vrfs.entrySet()) {
        Vrf vrf = c.getVrfs().get(entry.getKey());
        H3cModel.BgpVrf b = entry.getValue();
        if (vrf == null) {
          continue;
        }
        Ip routerId =
            b.routerId != null
                ? b.routerId
                : bgp.routerId != null ? bgp.routerId : vc.getRouterId();
        if (routerId == null) {
          routerId =
              vc.getInterfaces().values().stream()
                  .filter(i -> i.name.startsWith("LoopBack"))
                  .flatMap(i -> i.addresses.stream())
                  .map(a -> a.getIp())
                  .max(Ip::compareTo)
                  .orElse(Ip.ZERO);
        }
        BgpProcess process =
            BgpProcess.builder()
                .setVrf(vrf)
                .setRouterId(routerId)
                .setEbgpAdminCost(255)
                .setIbgpAdminCost(255)
                .setLocalAdminCost(130)
                .setLocalOriginationTypeTieBreaker(LocalOriginationTypeTieBreaker.PREFER_NETWORK)
                .setNetworkNextHopIpTieBreaker(NextHopIpTieBreaker.LOWEST_NEXT_HOP_IP)
                .setRedistributeNextHopIpTieBreaker(NextHopIpTieBreaker.HIGHEST_NEXT_HOP_IP)
                .build();
        process.setTieBreaker(BgpTieBreaker.ROUTER_ID);
        for (Map.Entry<String, H3cModel.Peer> pe : b.peers.entrySet()) {
          H3cModel.Peer peer = pe.getValue();
          Ip ip = Ip.tryParse(pe.getKey()).orElse(null);
          if (ip == null || !peer.enabled || peer.shutdown || peer.remoteAs == null) {
            continue;
          }
          String export = "~H3C_BGP_EXPORT:" + vrf.getName() + ":" + ip + "~";
          String importPolicy = "~H3C_BGP_IMPORT:" + vrf.getName() + ":" + ip + "~";
          RoutingPolicy.builder()
              .setOwner(c)
              .setName(importPolicy)
              .setStatements(
                  List.of(
                      new If(
                          call(c, peer.importPolicy),
                          List.of(Statements.ExitAccept.toStaticStatement())),
                      Statements.ExitReject.toStaticStatement()))
              .build();
          List<BooleanExpr> originated = new ArrayList<>();
          originated.add(new MatchProtocol(RoutingProtocol.BGP, RoutingProtocol.IBGP));
          b.networks.forEach(
              (prefix, policy) -> {
                WithEnvironmentExpr network = new WithEnvironmentExpr();
                network.setExpr(
                    new Conjunction(
                        List.of(
                            new MatchPrefixSet(
                                DestinationNetwork.instance(),
                                new ExplicitPrefixSet(
                                    new PrefixSpace(PrefixRange.fromPrefix(prefix)))),
                            call(c, policy))));
                network.setPostTrueStatements(
                    List.of(new SetOrigin(new LiteralOrigin(OriginType.IGP, null))));
                originated.add(network);
              });
          b.redistribution.forEach(
              (protocol, policy) ->
                  originated.add(new Conjunction(List.of(protocol(protocol), call(c, policy)))));
          List<Statement> accepted = new ArrayList<>();
          if (peer.nextHopSelf) {
            accepted.add(new SetNextHop(SelfNextHop.getInstance()));
          }
          if (peer.replaceAs) {
            accepted.add(
                new ReplaceAsesInAsSequence(
                    ReplaceAsesInAsSequence.sequenceOf(List.of(peer.remoteAs)),
                    ReplaceAsesInAsSequence.localAsOrConfedIfNeighborNotInConfed()));
          }
          accepted.add(Statements.ExitAccept.toStaticStatement());
          List<Statement> statements = new ArrayList<>();
          statements.add(
              new If(
                  new MatchProtocol(RoutingProtocol.BGP, RoutingProtocol.IBGP),
                  List.of(),
                  List.of(
                      new SetOrigin(new LiteralOrigin(OriginType.INCOMPLETE, null)),
                      new SetMetric(new LiteralLong(0)))));
          statements.add(
              new If(
                  new Conjunction(List.of(new Disjunction(originated), call(c, peer.exportPolicy))),
                  accepted));
          statements.add(Statements.ExitReject.toStaticStatement());
          RoutingPolicy.builder().setOwner(c).setName(export).setStatements(statements).build();
          Ip source = peer.sourceIp;
          if (source == null && peer.sourceInterface != null) {
            H3cModel.Interface i = vc.getInterfaces().get(peer.sourceInterface);
            if (i == null || !i.vrf.equals(vrf.getName()) || i.addresses.isEmpty()) {
              vc.getWarnings()
                  .redFlagf(
                      "H3C BGP peer %s has unusable source interface; peer not converted", ip);
              continue;
            }
            source = i.addresses.get(0).getIp();
          }
          BgpActivePeerConfig.builder()
              .setBgpProcess(process)
              .setPeerAddress(ip)
              .setLocalAs(bgp.asn)
              .setRemoteAsns(LongSpace.of(peer.remoteAs))
              .setLocalIp(source)
              .setDescription(peer.description)
              .setEbgpMultihop(peer.multihop)
              .setIpv4UnicastAddressFamily(
                  Ipv4UnicastAddressFamily.builder()
                      .setImportPolicy(importPolicy)
                      .setExportPolicy(export)
                      .setAddressFamilyCapabilities(
                          AddressFamilyCapabilities.builder()
                              .setAllowLocalAsIn(peer.allowAs > 0)
                              .setSendCommunity(peer.sendCommunity)
                              .setSendExtendedCommunity(peer.sendExtendedCommunity)
                              .build())
                      .build())
              .build();
        }
      }
    }
  }

  private static void warnLimitations(H3cConfiguration vc) {
    long v6Interfaces =
        vc.getInterfaces().values().stream().filter(i -> !i.ipv6Addresses.isEmpty()).count();
    long v6Peers =
        vc.getBgpProcesses().stream()
            .flatMap(b -> b.vrfs.values().stream())
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
              "H3C IPv6 retained, not simulated: %d addressed interfaces, %d static routes, %d BGP"
                  + " peers; IPv6 ISIS/SR not converted",
              v6Interfaces, vc.getIpv6StaticRoutes().size(), v6Peers);
    }
    if (!vc.getVsis().isEmpty()
        || !vc.getXconnects().isEmpty()
        || !vc.getLocators().isEmpty()
        || !vc.getVpns().isEmpty()) {
      vc.getWarnings()
          .redFlagf(
              "H3C EVPN/MPLS/SRv6 retained, not simulated: %d VPN instances, %d VSIs, %d xconnect"
                  + " groups, %d locators; no VNI or EVPN sessions fabricated",
              vc.getVpns().size(),
              vc.getVsis().size(),
              vc.getXconnects().size(),
              vc.getLocators().size());
    }
    if (unsupportedGuards > 0) {
      vc.getWarnings()
          .redFlagf(
              "H3C route-policy: %d nodes have RD/IPv6 next-hop matches; those matches converted to"
                  + " FALSE",
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
              "H3C route-policy: %d nodes disabled due to unsupported whole-match or invalid"
                  + " commands",
              disabledNodes);
    }
    long extraInstances =
        vc.getBgpProcesses().stream().filter(b -> !b.instance.equals("default")).count();
    if (extraInstances > 0) {
      vc.getWarnings()
          .redFlagf("H3C additional BGP instances retained, not converted: %d", extraInstances);
    }
    long operationalPeers =
        vc.getBgpProcesses().stream()
            .flatMap(b -> b.vrfs.values().stream())
            .flatMap(v -> v.peers.values().stream())
            .filter(p -> !p.retained.isEmpty() || p.allowAs > 0)
            .count();
    if (operationalPeers > 0) {
      vc.getWarnings()
          .redFlagf(
              "H3C BGP operational limitations on %d peers: timers/BFD/route-limit retained;"
                  + " allow-as-loop count represented as boolean",
              operationalPeers);
    }
  }

  private H3cConversions() {}
}
