package org.batfish.vendor.huawei.grammar;

import java.util.Set;
import org.antlr.v4.runtime.ParserRuleContext;
import org.batfish.common.NetworkSnapshot;
import org.batfish.common.Warnings;
import org.batfish.grammar.ControlPlaneExtractor;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.vendor.VendorConfiguration;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;

public final class HuaweiControlPlaneExtractor implements ControlPlaneExtractor {
  private final HuaweiCombinedParser _parser;
  private final Warnings _warnings;
  private final SilentSyntaxCollection _silentSyntax;
  private HuaweiConfiguration _configuration;

  public HuaweiControlPlaneExtractor(
      HuaweiCombinedParser parser, Warnings warnings, SilentSyntaxCollection silentSyntax) {
    _parser = parser;
    _warnings = warnings;
    _silentSyntax = silentSyntax;
  }

  @Override
  public Set<String> implementedRuleNames() {
    return Set.of("statement", "huawei_configuration");
  }

  @Override
  public VendorConfiguration getVendorConfiguration() {
    return _configuration;
  }

  @Override
  public void processParseTree(NetworkSnapshot snapshot, ParserRuleContext tree) {
    _configuration = new HuaweiConfiguration();
    _configuration.setWarnings(_warnings);
    new HuaweiFeatureExtractor(_configuration, _warnings, _silentSyntax)
        .extract(
            HuaweiStatementTree.build(_parser, (HuaweiParser.Huawei_configurationContext) tree));
  }
}
