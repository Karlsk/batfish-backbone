package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import java.io.InputStream;
import java.util.Map;
import org.batfish.datamodel.answers.ParseStatus;
import org.batfish.main.Batfish;
import org.batfish.main.BatfishTestUtils;
import org.batfish.main.TestrigText;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public final class HuaweiRawCaptureTest {
  @Rule public TemporaryFolder folder = new TemporaryFolder();

  @Test
  public void testR2Production() throws Exception {
    byte[] bytes;
    try (InputStream stream = getClass().getResourceAsStream("/NJ-SCT-R02")) {
      assumeTrue("Private R2 capture absent", stream != null);
      bytes = stream.readAllBytes();
    }
    Batfish batfish =
        BatfishTestUtils.getBatfishFromTestrigText(
            TestrigText.builder().setConfigurationBytes(Map.of("r2", bytes)).build(), folder);
    try {
      var vendors = batfish.loadVendorConfigurations(batfish.getSnapshot());
      var answer = batfish.loadParseVendorConfigurationAnswerElement(batfish.getSnapshot());
      assertEquals("huawei_vrp", answer.getFileFormats().get("configs/r2").getVendorString());
      var warnings = answer.getWarnings().get("configs/r2");
      assertTrue(
          warnings == null
              ? ""
              : warnings.getParseWarnings().stream()
                  .map(w -> w.getLine() + ":" + w.getText() + " " + w.getComment())
                  .toList()
                  .toString(),
          warnings == null || warnings.getParseWarnings().isEmpty());
      assertEquals(ParseStatus.PASSED, answer.getParseStatus().get("configs/r2"));
      assertEquals(1, vendors.size());
      var vc =
          (org.batfish.vendor.huawei.representation.HuaweiConfiguration)
              vendors.values().iterator().next();
      assertEquals(263, vc.getInterfaces().size());
      assertEquals(57, vc.getVpns().size());
      assertEquals(2, vc.getIsisProcesses().size());
      assertEquals(1, vc.getBgpProcesses().size());
      assertEquals(
          java.util.Map.of("BGP/ospf", 3L),
          vc.getUnsupportedRedistributions().stream()
              .collect(
                  java.util.stream.Collectors.groupingBy(
                      r -> r.target() + "/" + r.statement().words()[1],
                      java.util.stream.Collectors.counting())));
      assertEquals(27, vc.getPolicies().size());
      assertEquals(51, vc.getPolicies().values().stream().mapToInt(p -> p.nodes.size()).sum());
      assertEquals(15, vc.getEvpnInstances().size());
      assertEquals(5, vc.getBridgeDomains().size());
      assertEquals(2, vc.getEvpls().size());
      assertEquals(2, vc.getLocators().size());
      assertEquals(13, vc.getStaticRoutes().size());
      assertEquals(
          43,
          vc.getBgpProcesses().get(0).vrfs.values().stream()
              .flatMap(
                  v ->
                      org.batfish.vendor.huawei.representation.HuaweiBgpInheritance.ipv4Peers(v)
                          .entrySet()
                          .stream())
              .filter(
                  e ->
                      org.batfish.datamodel.Ip.tryParse(e.getKey()).isPresent()
                          && e.getValue().enabled
                          && !e.getValue().shutdown
                          && e.getValue().remoteAs != null)
              .count());
      var c = batfish.loadConfigurations(batfish.getSnapshot()).get("nj-sct-r02");
      assertNotNull(c);
      assertEquals(263, c.getAllInterfaces().size());
      assertEquals(59, c.getVrfs().size());
      assertEquals(org.batfish.datamodel.DeviceModel.HUAWEI_VRP_UNSPECIFIED, c.getDeviceModel());
      assertEquals(
          vc.getIsisProcesses().get(10).net,
          c.getDefaultVrf().getIsisProcess().getNetAddress().toString());
      assertTrue(
          c.getVrfs().values().stream()
              .allMatch(v -> v.getLayer2Vnis().isEmpty() && v.getLayer3Vnis().isEmpty()));
      assertTrue(c.getVrfs().values().stream().allMatch(v -> v.getVrfLeakConfig() == null));
      var peers =
          c.getVrfs().values().stream()
              .filter(v -> v.getBgpProcess() != null)
              .flatMap(v -> v.getBgpProcess().getActiveNeighbors().values().stream())
              .toList();
      assertTrue(peers.stream().allMatch(p -> p.getEvpnAddressFamily() == null));
      // Independent capture audit: 27 global + 16 VPN peers; three global source
      // interfaces have no IPv4 address, so their sessions cannot be represented.
      assertEquals(40, peers.size());
      assertEquals(24, c.getDefaultVrf().getBgpProcess().getActiveNeighbors().size());
      assertEquals(33, c.getVrfs().get("l3_3027").getBgpProcess().getEbgpAdminCost());
      assertEquals(2, c.getVrfs().get("l3_3193").getBgpProcess().getLocalAdminCost());
      assertEquals(
          Map.of(60, 10L, 120, 1L, 123, 1L, 125, 1L),
          vc.getStaticRoutes().stream()
              .collect(
                  java.util.stream.Collectors.groupingBy(
                      r -> r.preference, java.util.stream.Collectors.counting())));
      assertEquals(
          Map.of(60L, 10L, 120L, 1L, 123L, 1L, 125L, 1L),
          c.getVrfs().values().stream()
              .flatMap(v -> v.getStaticRoutes().stream())
              .collect(
                  java.util.stream.Collectors.groupingBy(
                      r -> r.getAdministrativeCost(), java.util.stream.Collectors.counting())));
      var conversion =
          batfish.loadConvertConfigurationAnswerElementOrReparse(batfish.getSnapshot());
      var allowed =
          java.util.Set.of(
              "Huawei ISIS:",
              "Huawei IPv6 retained, not simulated:",
              "Huawei EVPN/MPLS/SRv6 retained, not simulated:",
              "Huawei route-policy:",
              "Huawei OSPF retained, not simulated:",
              "Huawei BGP operational limitations");
      var redFlags = conversion.getWarnings().get("nj-sct-r02").getRedFlagWarnings();
      assertEquals(8, redFlags.size());
      for (String prefix : allowed) {
        assertTrue(prefix, redFlags.stream().anyMatch(w -> w.getText().startsWith(prefix)));
      }
      assertTrue(
          redFlags.stream().map(w -> w.getText()).toList().toString(),
          redFlags.stream()
              .allMatch(w -> allowed.stream().anyMatch(p -> w.getText().startsWith(p))));
    } catch (RuntimeException e) {
      throw new AssertionError("Raw R2 production failure; diagnostics intentionally redacted");
    }
  }
}
