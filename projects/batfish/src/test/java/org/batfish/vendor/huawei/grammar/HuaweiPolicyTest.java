package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.batfish.datamodel.Bgpv4Route;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.bgp.community.StandardCommunity;
import org.batfish.datamodel.routing_policy.Environment;
import org.batfish.datamodel.routing_policy.communities.CommunitySet;
import org.junit.Test;

public final class HuaweiPolicyTest {
  private static Bgpv4Route route(String prefix, boolean community) {
    return Bgpv4Route.testBuilder()
        .setNetwork(Prefix.parse(prefix))
        .setOriginatorIp(Ip.parse("1.1.1.1"))
        .setProtocol(RoutingProtocol.BGP)
        .setCommunities(
            community
                ? CommunitySet.of(StandardCommunity.parse("65000:100"))
                : CommunitySet.empty())
        .build();
  }

  @Test
  public void testOrderedOrAndActions() {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            ip ip-prefix A index 10 deny 10.1.0.0 16
            ip ip-prefix A index 20 permit 10.0.0.0 8 greater-equal 16 less-equal 24
            ip ip-prefix B index 10 permit 192.0.2.0 24
            ip community-filter basic C permit 65000:100
            route-policy P permit node 20
             if-match ip-prefix A B
             if-match community-filter C
             apply community 100 200 additive
             apply cost 28
             apply local-preference 134
             apply ip-address next-hop 192.0.2.1
            #
            route-policy P deny node 10
             if-match ip-prefix B
            #
            """);
    assertFalse(vc.getUnrecognized());
    var policy = vc.toVendorIndependentConfigurations().get(0).getRoutingPolicies().get("P");
    var in = route("10.2.0.0/16", true);
    var out = in.toBuilder();
    assertTrue(policy.process(in, out, Environment.Direction.OUT));
    assertEquals(28, out.getMetric());
    assertEquals(134, out.getLocalPreference());
    assertEquals(3, out.getCommunities().getCommunities().size());
    for (var rejected :
        new Bgpv4Route[] {
          route("10.1.0.0/16", true),
          route("192.0.2.0/24", true),
          route("10.2.0.0/16", false),
          route("10.2.0.0/25", true)
        }) {
      assertFalse(policy.process(rejected, rejected.toBuilder(), Environment.Direction.OUT));
    }
  }

  @Test
  public void testUnsupportedAndUndefinedGuardsDeny() {
    for (String guard :
        new String[] {
          "if-match rd-filter R",
          "if-match ipv6 next-hop prefix-list V6",
          "if-match ip-prefix MISSING"
        }) {
      var vc =
          HuaweiGrammarTest.parse("sysname r2\nroute-policy P permit node 10\n " + guard + "\n#\n");
      var c = vc.toVendorIndependentConfigurations().get(0);
      var in = route("192.0.2.0/24", true);
      assertFalse(
          c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
      if (guard.contains("rd-filter")) {
        assertFalse(vc.getUnrecognized());
      }
    }
  }

  @Test
  public void testCommunityReplaceColorAndExtcommunityOrder() {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            ip extcommunity-filter basic RT index 20 permit rt 65000:1
            ip extcommunity-filter basic RT index 10 deny rt 65000:2
            route-policy P permit node 10
             if-match extcommunity-filter RT
             apply community 100:100 internet
             apply extcommunity color 0:500
            #
            """);
    assertFalse(vc.getUnrecognized());
    var policy = vc.toVendorIndependentConfigurations().get(0).getRoutingPolicies().get("P");
    var rt = org.batfish.datamodel.bgp.community.ExtendedCommunity.target(65000, 1);
    var in =
        route("192.0.2.0/24", true).toBuilder()
            .setCommunities(CommunitySet.of(rt, StandardCommunity.parse("65000:100")))
            .build();
    var out = in.toBuilder();
    assertTrue(policy.process(in, out, Environment.Direction.OUT));
    assertTrue(out.getCommunities().getCommunities().contains(rt));
    assertFalse(
        out.getCommunities().getCommunities().contains(StandardCommunity.parse("65000:100")));
    assertTrue(out.getCommunities().getCommunities().contains(StandardCommunity.parse("100:100")));
    assertTrue(
        out.getCommunities()
            .getCommunities()
            .contains(org.batfish.datamodel.bgp.community.ExtendedCommunity.opaque(true, 11, 500)));
    var denied =
        in.toBuilder()
            .setCommunities(
                CommunitySet.of(
                    rt, org.batfish.datamodel.bgp.community.ExtendedCommunity.target(65000, 2)))
            .build();
    assertFalse(policy.process(denied, denied.toBuilder(), Environment.Direction.OUT));
  }
}
