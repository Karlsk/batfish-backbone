package org.batfish.vendor.h3c.grammar;

import java.util.Set;
import org.antlr.v4.runtime.ParserRuleContext;
import org.batfish.common.NetworkSnapshot;
import org.batfish.common.Warnings;
import org.batfish.grammar.ControlPlaneExtractor;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.vendor.VendorConfiguration;
import org.batfish.vendor.h3c.representation.H3cConfiguration;

public final class H3cControlPlaneExtractor implements ControlPlaneExtractor {
  private final H3cCombinedParser _parser;
  private final Warnings _warnings;
  private final SilentSyntaxCollection _silentSyntax;
  private H3cConfiguration _configuration;

  public H3cControlPlaneExtractor(
      H3cCombinedParser parser, Warnings warnings, SilentSyntaxCollection silentSyntax) {
    _parser = parser;
    _warnings = warnings;
    _silentSyntax = silentSyntax;
  }

  @Override
  public Set<String> implementedRuleNames() {
    return Set.of("statement", "h3c_configuration");
  }

  @Override
  public VendorConfiguration getVendorConfiguration() {
    return _configuration;
  }

  @Override
  public void processParseTree(NetworkSnapshot snapshot, ParserRuleContext tree) {
    _configuration = new H3cConfiguration();
    _configuration.setWarnings(_warnings);
    new H3cFeatureExtractor(_configuration, _warnings, _silentSyntax)
        .extract(H3cStatementTree.build(_parser, (H3cParser.H3c_configurationContext) tree));
  }
}
