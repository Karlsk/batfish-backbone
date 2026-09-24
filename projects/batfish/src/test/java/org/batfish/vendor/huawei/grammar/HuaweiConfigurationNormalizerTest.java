package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public final class HuaweiConfigurationNormalizerTest {
  @Test
  public void testWhitespaceOnlyLinesPreserveMappingAndCommandIndentation() {
    var n =
        HuaweiConfigurationNormalizer.normalize(
            "sysname r1\n"
                + " \n"
                + "\t\n"
                + " \t \n"
                + "isis 10\n"
                + " is-level level-2\n"
                + "  network-entity 49.0001.0000.0000.0001.00\n"
                + "#\n");
    assertEquals(
        "sysname r1\n\n\n\n"
            + "isis 10\n"
            + " is-level level-2\n"
            + "  network-entity 49.0001.0000.0000.0001.00\n"
            + "#\n",
        n.text());
    assertEquals(java.util.List.of(1, 2, 3, 4, 5, 6, 7, 8), n.originalLines());
  }

  @Test
  public void testPagerIndentationAndOriginalLines() {
    var n =
        HuaweiConfigurationNormalizer.normalize(
            "<r2>dis cur\r\r\n"
                + "interface GE1/0/0\r\n"
                + "  ---- More ----\u001b[16D                \u001b[16D ip address 10.0.0.1 24\r"
                + "#\r\n"
                + "[~r2]\r\n"
                + "sysname rX\b2\n");
    assertEquals("\ninterface GE1/0/0\n ip address 10.0.0.1 24\n#\n\nsysname r2\n", n.text());
    assertEquals(3, n.originalLine(3));
    assertEquals(6, n.originalLine(6));
  }
}
