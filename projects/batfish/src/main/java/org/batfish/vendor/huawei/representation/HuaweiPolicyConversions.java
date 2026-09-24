package org.batfish.vendor.huawei.representation;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.LineAction;
import org.batfish.datamodel.RouteFilterLine;
import org.batfish.datamodel.RouteFilterList;
import org.batfish.datamodel.SubRange;
import org.batfish.datamodel.bgp.community.Community;
import org.batfish.datamodel.bgp.community.ExtendedCommunity;
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
import org.batfish.datamodel.routing_policy.communities.CommunitySetMatchAll;
import org.batfish.datamodel.routing_policy.communities.CommunitySetMatchExpr;
import org.batfish.datamodel.routing_policy.communities.CommunitySetUnion;
import org.batfish.datamodel.routing_policy.communities.HasCommunity;
import org.batfish.datamodel.routing_policy.communities.InputCommunities;
import org.batfish.datamodel.routing_policy.communities.LiteralCommunitySet;
import org.batfish.datamodel.routing_policy.communities.MatchCommunities;
import org.batfish.datamodel.routing_policy.communities.SetCommunities;
import org.batfish.datamodel.routing_policy.expr.BooleanExpr;
import org.batfish.datamodel.routing_policy.expr.BooleanExprs;
import org.batfish.datamodel.routing_policy.expr.Conjunction;
import org.batfish.datamodel.routing_policy.expr.DestinationNetwork;
import org.batfish.datamodel.routing_policy.expr.Disjunction;
import org.batfish.datamodel.routing_policy.expr.IpNextHop;
import org.batfish.datamodel.routing_policy.expr.LiteralLong;
import org.batfish.datamodel.routing_policy.expr.MatchPrefixSet;
import org.batfish.datamodel.routing_policy.expr.NamedPrefixSet;
import org.batfish.datamodel.routing_policy.statement.If;
import org.batfish.datamodel.routing_policy.statement.SetLocalPreference;
import org.batfish.datamodel.routing_policy.statement.SetMetric;
import org.batfish.datamodel.routing_policy.statement.SetNextHop;
import org.batfish.datamodel.routing_policy.statement.Statement;
import org.batfish.datamodel.routing_policy.statement.Statements;

/** Ordered Huawei filter matching and policy actions. */
final class HuaweiPolicyConversions {
  static void convert(HuaweiConfiguration vc, Configuration c) {
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
              for (HuaweiModel.PolicyNode node : policy.nodes.values()) {
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
                  CommunitySetExpr communities = InputCommunities.instance();
                  for (HuaweiStatement action : node.actions) {
                    Statement converted = action(action, communities);
                    if (converted instanceof SetCommunities set) {
                      communities = set.getCommunitySetExpr();
                    } else {
                      onMatch.add(converted);
                    }
                  }
                  if (!(communities instanceof InputCommunities)) {
                    // Compose community actions so a subsequent color action cannot reset
                    // earlier standard-community replacement to the original route's values.
                    onMatch.add(new SetCommunities(communities));
                  }
                }
                onMatch.add(terminal(node.permit));
                statements.add(new If(new Conjunction(conjuncts), onMatch));
              }
              statements.add(terminal(false));
              RoutingPolicy.builder().setOwner(c).setName(name).setStatements(statements).build();
            });
  }

  private static BooleanExpr match(
      HuaweiConfiguration vc, Configuration c, String kind, String name) {
    return switch (kind) {
      case "prefix" ->
          c.getRouteFilterLists().containsKey(name)
              ? new MatchPrefixSet(DestinationNetwork.instance(), new NamedPrefixSet(name))
              : BooleanExprs.FALSE;
      case "community", "extcommunity" -> communityMatch(vc, kind.equals("extcommunity"), name);
      // Existing VI routes have neither IPv6 next-hop nor a route distinguisher to match.
      default -> BooleanExprs.FALSE;
    };
  }

  private static BooleanExpr communityMatch(HuaweiConfiguration vc, boolean ext, String name) {
    Map<Integer, HuaweiModel.CommunityEntry> entries =
        (ext ? vc.getExtcommunities() : vc.getCommunities()).get(name);
    if (entries == null
        || (ext ? vc.getInvalidExtcommunities() : vc.getInvalidCommunities()).contains(name)) {
      return BooleanExprs.FALSE;
    }
    List<CommunitySetAclLine> lines = new ArrayList<>();
    for (HuaweiModel.CommunityEntry entry : entries.values()) {
      if (entry.regex()) {
        vc.getWarnings()
            .redFlagf("Huawei advanced community list %s is not converted; match disabled", name);
        return BooleanExprs.FALSE;
      }
      List<CommunityMatchExpr> values = new ArrayList<>();
      List<? extends Community> communities =
          ext
              ? HuaweiCommunity.parseExtendedValues(entry.values())
              : entry.values().stream().map(HuaweiCommunity::parse).toList();
      for (Community community : communities) {
        values.add(new CommunityIs(community));
      }
      lines.add(
          new CommunitySetAclLine(
              entry.permit() ? LineAction.PERMIT : LineAction.DENY,
              ext
                  ? new HasCommunity(new CommunityMatchAny(values))
                  // A standard basic entry is a subset test, not an exact-set match.
                  : CommunitySetMatchAll.matchAll(
                      values.stream().<CommunitySetMatchExpr>map(HasCommunity::new).toList())));
    }
    return new MatchCommunities(InputCommunities.instance(), new CommunitySetAcl(lines));
  }

  private static Statement action(HuaweiStatement s, CommunitySetExpr inputCommunities) {
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
            communities.add(HuaweiCommunity.parse(a[p]));
          }
        }
        CommunitySetExpr original = inputCommunities;
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

  private HuaweiPolicyConversions() {}
}
