package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.batfish.datamodel.route.nh.NextHopVrf;
import org.junit.Test;

public final class HuaweiStaticRouteTest {
  @Test
  public void testNextTablePublicAndExplicitNextHopBoundary() {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            ip vpn-instance blue
            #
            ip route-static vpn-instance blue 203.0.113.0 24 public
            ip route-static 198.51.100.0 24 vpn-instance blue
            ip route-static 192.0.2.0 24 vpn-instance blue 10.0.0.1
            ip route-static 192.0.3.0 24 vpn-instance blue 10.0.0.2
            """);
    assertTrue(vc.getWarnings().getParseWarnings().isEmpty());
    var c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals(
        NextHopVrf.of("default"), c.getVrfs().get("blue").getStaticRoutes().first().getNextHop());
    assertEquals(1, c.getDefaultVrf().getStaticRoutes().size());
    assertEquals(NextHopVrf.of("blue"), c.getDefaultVrf().getStaticRoutes().first().getNextHop());
    assertEquals(4, vc.getStaticRoutes().size());
    assertEquals(1, vc.getWarnings().getRedFlagWarnings().size());
    assertTrue(
        vc.getWarnings()
            .getRedFlagWarnings()
            .iterator()
            .next()
            .getText()
            .startsWith("Huawei static: 2 routes"));
  }
}
