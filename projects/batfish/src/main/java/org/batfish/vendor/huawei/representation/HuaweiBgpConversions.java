package org.batfish.vendor.huawei.representation;

import static org.batfish.vendor.huawei.representation.HuaweiConversions.call;
import static org.batfish.vendor.huawei.representation.HuaweiConversions.protocol;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.batfish.datamodel.BgpActivePeerConfig;
import org.batfish.datamodel.BgpProcess;
import org.batfish.datamodel.BgpTieBreaker;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.LongSpace;
import org.batfish.datamodel.OriginType;
import org.batfish.datamodel.PrefixRange;
import org.batfish.datamodel.PrefixSpace;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.Vrf;
import org.batfish.datamodel.bgp.AddressFamilyCapabilities;
import org.batfish.datamodel.bgp.Ipv4UnicastAddressFamily;
import org.batfish.datamodel.bgp.LocalOriginationTypeTieBreaker;
import org.batfish.datamodel.bgp.NextHopIpTieBreaker;
import org.batfish.datamodel.routing_policy.RoutingPolicy;
import org.batfish.datamodel.routing_policy.expr.BooleanExpr;
import org.batfish.datamodel.routing_policy.expr.BooleanExprs;
import org.batfish.datamodel.routing_policy.expr.Conjunction;
import org.batfish.datamodel.routing_policy.expr.DestinationNetwork;
import org.batfish.datamodel.routing_policy.expr.Disjunction;
import org.batfish.datamodel.routing_policy.expr.ExplicitPrefixSet;
import org.batfish.datamodel.routing_policy.expr.LiteralLong;
import org.batfish.datamodel.routing_policy.expr.LiteralOrigin;
import org.batfish.datamodel.routing_policy.expr.MatchPrefixSet;
import org.batfish.datamodel.routing_policy.expr.MatchProtocol;
import org.batfish.datamodel.routing_policy.expr.SelfNextHop;
import org.batfish.datamodel.routing_policy.expr.WithEnvironmentExpr;
import org.batfish.datamodel.routing_policy.statement.If;
import org.batfish.datamodel.routing_policy.statement.ReplaceAsesInAsSequence;
import org.batfish.datamodel.routing_policy.statement.SetMetric;
import org.batfish.datamodel.routing_policy.statement.SetNextHop;
import org.batfish.datamodel.routing_policy.statement.SetOrigin;
import org.batfish.datamodel.routing_policy.statement.Statement;
import org.batfish.datamodel.routing_policy.statement.Statements;

/** IPv4 BGP conversion from independently resolved VRP scopes. */
final class HuaweiBgpConversions {
  static void convert(HuaweiConfiguration vc, Configuration c) {
    int unusableSources = 0;
    for (HuaweiModel.Bgp bgp : vc.getBgpProcesses()) {
      if (!bgp.instance.equals("default")) {
        continue;
      }
      for (Map.Entry<String, HuaweiModel.BgpVrf> entry : bgp.vrfs.entrySet()) {
        Vrf vrf = c.getVrfs().get(entry.getKey());
        HuaweiModel.BgpVrf base = entry.getValue();
        HuaweiModel.BgpVrf b = base.families.get("ipv4-family unicast");
        if (b == null) {
          b = base;
        }
        HuaweiModel.BgpVrf ipv4 = b;
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
                  .orElseGet(
                      () ->
                          vc.getInterfaces().values().stream()
                              .flatMap(i -> i.addresses.stream())
                              .map(a -> a.getIp())
                              .max(Ip::compareTo)
                              .orElse(Ip.ZERO));
        }
        BgpProcess process =
            BgpProcess.builder()
                .setVrf(vrf)
                .setRouterId(routerId)
                .setEbgpAdminCost(ipv4.ebgpPreference)
                .setIbgpAdminCost(ipv4.ibgpPreference)
                .setLocalAdminCost(ipv4.localPreference)
                .setLocalOriginationTypeTieBreaker(LocalOriginationTypeTieBreaker.PREFER_NETWORK)
                .setNetworkNextHopIpTieBreaker(NextHopIpTieBreaker.LOWEST_NEXT_HOP_IP)
                .setRedistributeNextHopIpTieBreaker(NextHopIpTieBreaker.HIGHEST_NEXT_HOP_IP)
                .build();
        process.setTieBreaker(BgpTieBreaker.ROUTER_ID);
        for (Map.Entry<String, HuaweiModel.Peer> pe :
            HuaweiBgpInheritance.ipv4Peers(base).entrySet()) {
          HuaweiModel.Peer peer = pe.getValue();
          Ip ip = Ip.tryParse(pe.getKey()).orElse(null);
          if (ip == null || !peer.enabled || peer.shutdown || peer.remoteAs == null) {
            continue;
          }
          String export = "~Huawei_BGP_EXPORT:" + vrf.getName() + ":" + ip + "~";
          String importPolicy = "~Huawei_BGP_IMPORT:" + vrf.getName() + ":" + ip + "~";
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
              (protocol, rule) -> {
                WithEnvironmentExpr redistribution = new WithEnvironmentExpr();
                redistribution.setPreStatements(
                    List.of(
                        new SetMetric(new LiteralLong(rule.metric() == null ? 0 : rule.metric()))));
                redistribution.setExpr(call(c, rule.policy()));
                originated.add(
                    new Conjunction(
                        List.of(
                            protocol(protocol),
                            ipv4.importDefaultRoute
                                ? BooleanExprs.TRUE
                                : HuaweiConversions.notDefaultRoute(),
                            redistribution)));
              });
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
            HuaweiModel.Interface i = vc.getInterfaces().get(peer.sourceInterface);
            if (i == null || !i.vrf.equals(vrf.getName()) || i.addresses.isEmpty()) {
              unusableSources++;
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
              .setClusterId(peer.reflectClient ? routerId.asLong() : null)
              .setEbgpMultihop(peer.multihop)
              .setIpv4UnicastAddressFamily(
                  Ipv4UnicastAddressFamily.builder()
                      .setRouteReflectorClient(peer.reflectClient)
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
    if (unusableSources > 0) {
      vc.getWarnings()
          .redFlagf(
              "Huawei BGP operational limitations: %d peers have unusable source interfaces; peers"
                  + " not converted",
              unusableSources);
    }
  }

  private HuaweiBgpConversions() {}
}
