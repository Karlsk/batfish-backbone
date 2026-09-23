package org.batfish.vendor.h3c.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNotSame;
import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import java.io.InputStream;
import java.nio.charset.Charset;
import java.util.Map;
import java.util.Set;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.ConfigurationFormat;
import org.batfish.datamodel.answers.ParseStatus;
import org.batfish.grammar.VendorConfigurationFormatDetector;
import org.batfish.main.Batfish;
import org.batfish.main.BatfishTestUtils;
import org.batfish.main.TestrigText;
import org.batfish.vendor.h3c.representation.H3cConfiguration;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Original byte captures exercise encoding detection, parsing, serialization and conversion. */
public final class H3cRawCaptureTest {
  @Rule public TemporaryFolder folder = new TemporaryFolder();

  private static byte[] capture(String name) throws Exception {
    try (InputStream stream = H3cRawCaptureTest.class.getResourceAsStream("/" + name)) {
      assumeTrue("Private capture not installed; see docs/configuration/README.md", stream != null);
      return stream.readAllBytes();
    }
  }

  @Test
  public void testR1ThroughProductionSnapshot() throws Exception {
    Batfish batfish =
        BatfishTestUtils.getBatfishFromTestrigText(
            TestrigText.builder().setConfigurationBytes(Map.of("r1", capture("NJ_SCT_R1"))).build(),
            folder);
    H3cConfiguration vc;
    try {
      vc =
          (H3cConfiguration)
              batfish.loadVendorConfigurations(batfish.getSnapshot()).get("nj-sct-r01");
    } catch (RuntimeException e) {
      // Parser exceptions include surrounding source lines. Never print raw capture contents.
      throw new AssertionError("R1 production parsing failed; reproduce with a sanitized fixture");
    }
    assertNotNull(vc);
    var parse = batfish.loadParseVendorConfigurationAnswerElement(batfish.getSnapshot());
    // Diagnostics contain only command heads and line numbers, never raw credentials.
    var warnings = parse.getWarnings().get("configs/r1");
    assertTrue(
        warnings == null
            ? ""
            : warnings.getParseWarnings().stream()
                .map(w -> w.getLine() + ": " + w.getText() + " " + w.getComment())
                .toList()
                .toString(),
        warnings == null || warnings.getParseWarnings().isEmpty());
    assertEquals(ParseStatus.PASSED, parse.getParseStatus().get("configs/r1"));
    assertEquals(ConfigurationFormat.H3C_COMWARE, parse.getFileFormats().get("configs/r1"));
    assertEquals(195, vc.getInterfaces().size());
    assertEquals(41, vc.getVpns().size());
    assertEquals(4, vc.getIsisProcesses().size());
    assertEquals(2, vc.getBgpProcesses().size());
    assertEquals(26, vc.getPolicies().values().stream().mapToInt(p -> p.nodes.size()).sum());
    assertEquals(10, vc.getVsis().size());
    assertEquals(4, vc.getXconnects().size());
    assertEquals(16, vc.getStaticRoutes().size());
    assertEquals(9, vc.getIpv6StaticRoutes().size());
    Configuration c = batfish.loadConfigurations(batfish.getSnapshot()).get("nj-sct-r01");
    assertNotNull(c);
    assertEquals(
        "missing interfaces: "
            + vc.getInterfaces().keySet().stream()
                .filter(n -> !c.getAllInterfaces().containsKey(n))
                .toList(),
        195,
        c.getAllInterfaces().size());
    assertEquals(
        vc.getIsisProcesses().get(10).net,
        c.getDefaultVrf().getIsisProcess().getNetAddress().toString());
    assertTrue(
        c.getVrfs().values().stream()
            .allMatch(v -> v.getLayer2Vnis().isEmpty() && v.getLayer3Vnis().isEmpty()));
    assertTrue(
        c.getVrfs().values().stream()
            .filter(v -> v.getBgpProcess() != null)
            .flatMap(
                v ->
                    com.google.common.collect.Streams.stream(v.getBgpProcess().getAllPeerConfigs()))
            .allMatch(p -> p.getEvpnAddressFamily() == null));
    var conversion = batfish.loadConvertConfigurationAnswerElementOrReparse(batfish.getSnapshot());
    Set<String> allowed =
        Set.of(
            "H3C ISIS: selected process 10;",
            "H3C IPv6 retained, not simulated:",
            "H3C EVPN/MPLS/SRv6 retained, not simulated:",
            "H3C route-policy:",
            "H3C additional BGP instances retained, not converted:",
            "H3C BGP operational limitations on");
    var redFlags = conversion.getWarnings().get("nj-sct-r01").getRedFlagWarnings();
    assertEquals(allowed.size(), redFlags.size());
    for (String prefix : allowed) {
      assertTrue(prefix, redFlags.stream().anyMatch(w -> w.getText().startsWith(prefix)));
    }
  }

  @Test
  public void testHuaweiIsNotH3c() throws Exception {
    String text = new String(capture("NJ-SCT-R02"), Charset.forName("GB18030"));
    assertNotSame(
        ConfigurationFormat.H3C_COMWARE,
        VendorConfigurationFormatDetector.identifyConfigurationFormat(text));
  }
}
