package org.batfish.vendor.h3c.grammar;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public final class H3cConfigurationNormalizerTest {
  @Test
  public void testBlankLinesKeepTheirPositions() {
    H3cConfigurationNormalizer.Result result =
        H3cConfigurationNormalizer.normalize("sysname r1\r\r\n \r\r\ninterface LoopBack0\r\r\n");
    assertEquals("sysname r1\n\ninterface LoopBack0\n", result.text());
    assertEquals(3, result.originalLine(3));
  }

  @Test
  public void testPagerPreservesFollowingIndentationAndLine() {
    H3cConfigurationNormalizer.Result result =
        H3cConfigurationNormalizer.normalize(
            "interface LoopBack0\r\r\n"
                + "---- More ----\r\r"
                + "               \r"
                + " ip address 10.0.0.1 32\r\r\n");
    assertEquals("interface LoopBack0\n ip address 10.0.0.1 32\n", result.text());
    assertEquals(2, result.originalLine(2));
  }

  @Test
  public void testAnsiAndPromptAndStandaloneCr() {
    H3cConfigurationNormalizer.Result result =
        H3cConfigurationNormalizer.normalize(
            "<r1>display current-configuration\r\n"
                + "sysname r1\r"
                + "\u001b[16D---- More ----\u001b[16D                \u001b[16Dinterface"
                + " LoopBack0\n");
    assertEquals("\nsysname r1\ninterface LoopBack0\n", result.text());
    assertEquals(3, result.originalLine(3));
  }
}
