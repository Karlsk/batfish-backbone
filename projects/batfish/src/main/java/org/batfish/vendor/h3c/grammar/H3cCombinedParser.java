package org.batfish.vendor.h3c.grammar;

import org.batfish.grammar.BatfishANTLRErrorStrategy;
import org.batfish.grammar.BatfishCombinedParser;
import org.batfish.grammar.BatfishLexerRecoveryStrategy;
import org.batfish.grammar.GrammarSettings;

public final class H3cCombinedParser extends BatfishCombinedParser<H3cParser, H3cLexer> {
  private final H3cConfigurationNormalizer.Result _normalized;

  public H3cCombinedParser(String input, GrammarSettings settings) {
    this(H3cConfigurationNormalizer.normalize(input), settings);
  }

  private H3cCombinedParser(
      H3cConfigurationNormalizer.Result normalized, GrammarSettings settings) {
    super(
        H3cParser.class,
        H3cLexer.class,
        normalized.text(),
        settings,
        new BatfishANTLRErrorStrategy.BatfishANTLRErrorStrategyFactory(H3cLexer.NEWLINE, "\n"),
        BatfishLexerRecoveryStrategy.WHITESPACE_AND_NEWLINES);
    _normalized = normalized;
  }

  public int originalLine(int line) {
    return _normalized.originalLine(line);
  }

  @Override
  public H3cParser.H3c_configurationContext parse() {
    return _parser.h3c_configuration();
  }
}
