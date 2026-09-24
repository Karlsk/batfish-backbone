package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.batfish.vendor.huawei.representation.HuaweiStructureType;
import org.junit.Test;

public final class HuaweiEvpnTest {
  @Test
  public void testTypedServicesAndSafeConversion() {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            ip vpn-instance blue
             ipv4-family
              route-distinguisher 65000:1
              vpn-target 65000:2 both evpn
            #
            evpn vpn-instance E bd-mode
             route-distinguisher 65000:10
             vpn-target 65000:20 both
             segment-routing ipv6 locator L
            #
            bridge-domain 10
             evpn binding vpn-instance E
            #
            evpl instance 1
             evpn binding vpn-instance E
             local-service-id 100 remote-service-id 200
            #
            segment-routing ipv6
             locator L ipv6-prefix 2001:db8:: 64 static 32
              opcode ::1 end-dt4 vpn-instance blue
              opcode ::2 end-dt2u bridge-domain 10
            #
            interface GE1/0/0.10 mode l2
             encapsulation dot1q vid 10
             bridge-domain 10
            #
            """);
    assertFalse(vc.getWarnings().getParseWarnings().toString(), vc.getUnrecognized());
    assertEquals("65000:10", vc.getEvpnInstances().get("E").rd);
    assertEquals(java.util.List.of("65000:20"), vc.getEvpnInstances().get("E").importTargets);
    assertEquals("E", vc.getBridgeDomains().get(10).vpn);
    assertEquals(Long.valueOf(200), vc.getEvpls().get("1").remoteServiceId);
    assertEquals("blue", vc.getLocators().get("L").opcodes.get("::1").vpn);
    assertEquals(Integer.valueOf(10), vc.getLocators().get("L").opcodes.get("::2").bridgeDomain);
    assertTrue(
        vc.getStructureManager()
            .getStructureReferences(HuaweiStructureType.LOCATOR)
            .containsKey("L"));
    var c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals("65000:1", c.getVrfs().get("blue").getRouteDistinguisher().toString());
    assertTrue(
        c.getVrfs().values().stream()
            .allMatch(v -> v.getLayer2Vnis().isEmpty() && v.getLayer3Vnis().isEmpty()));
    assertNull(c.getVrfs().get("blue").getVrfLeakConfig());
  }

  @Test
  public void testOrdinaryVrfDoesNotWarnEvpn() {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r2\nip vpn-instance blue\n ipv4-family\n  route-distinguisher 65000:1\n#\n");
    vc.toVendorIndependentConfigurations();
    assertTrue(vc.getWarnings().getRedFlagWarnings().isEmpty());
  }
}
