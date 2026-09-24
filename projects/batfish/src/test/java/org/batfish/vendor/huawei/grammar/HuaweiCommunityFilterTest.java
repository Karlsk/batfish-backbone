package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.batfish.datamodel.Bgpv4Route;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.bgp.community.Community;
import org.batfish.datamodel.bgp.community.ExtendedCommunity;
import org.batfish.datamodel.bgp.community.StandardCommunity;
import org.batfish.datamodel.routing_policy.Environment;
import org.batfish.datamodel.routing_policy.RoutingPolicy;
import org.batfish.datamodel.routing_policy.communities.CommunitySet;
import org.junit.Test;

public final class HuaweiCommunityFilterTest {
  private static final StandardCommunity A = StandardCommunity.parse("100:1");
  private static final StandardCommunity B = StandardCommunity.parse("200:1");

  private static RoutingPolicy policy(String entries, String kind) {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r2\n"
                + entries
                + "route-policy P permit node 10\n if-match "
                + kind
                + "-filter C\n#\n");
    assertFalse(vc.getUnrecognized());
    return vc.toVendorIndependentConfigurations().get(0).getRoutingPolicies().get("P");
  }

  private static boolean accepts(RoutingPolicy policy, Community... communities) {
    var route =
        Bgpv4Route.testBuilder()
            .setNetwork(Prefix.parse("192.0.2.0/24"))
            .setOriginatorIp(Ip.parse("192.0.2.1"))
            .setProtocol(RoutingProtocol.BGP)
            .setCommunities(CommunitySet.of(communities))
            .build();
    return policy.process(route, route.toBuilder(), Environment.Direction.OUT);
  }

  @Test
  public void testStandardEntryRequiresAllValues() {
    var p = policy("ip community-filter basic C permit 100:1 200:1\n", "community");
    assertFalse(accepts(p, A));
    assertFalse(accepts(p, B));
    assertTrue(accepts(p, A, B));
    assertTrue(accepts(p, A, B, StandardCommunity.parse("300:1")));
    assertFalse(accepts(p));
  }

  @Test
  public void testStandardDenyRequiresAllBeforeLaterPermit() {
    // Deliberately reverse source order: index 10 must take precedence over index 20.
    var p =
        policy(
            "ip community-filter basic C index 20 permit 100:1\n"
                + "ip community-filter basic C index 10 deny 100:1 200:1\n",
            "community");
    assertTrue(accepts(p, A));
    assertFalse(accepts(p, B));
    assertFalse(accepts(p, A, B));
  }

  @Test
  public void testSeparateStandardEntriesAreAlternatives() {
    var p =
        policy(
            "ip community-filter basic C index 10 permit 100:1\n"
                + "ip community-filter basic C index 20 permit 200:1\n",
            "community");
    assertTrue(accepts(p, A));
    assertTrue(accepts(p, B));
    assertTrue(accepts(p, A, B));
    assertFalse(accepts(p));
  }

  @Test
  public void testExtendedEntryStillMatchesAnyValue() {
    var p = policy("ip extcommunity-filter basic C permit rt 100:1 200:1\n", "extcommunity");
    var a = ExtendedCommunity.target(100, 1);
    var b = ExtendedCommunity.target(200, 1);
    assertTrue(accepts(p, a));
    assertTrue(accepts(p, b));
    assertTrue(accepts(p, a, b));
    assertFalse(accepts(p, A, B));
    assertFalse(accepts(p));
  }
}
