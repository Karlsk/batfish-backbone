package org.batfish.vendor.huawei.grammar;

import org.batfish.grammar.BatfishANTLRErrorStrategy;
import org.batfish.grammar.BatfishCombinedParser;
import org.batfish.grammar.BatfishLexerRecoveryStrategy;
import org.batfish.grammar.GrammarSettings;

public final class HuaweiCombinedParser extends BatfishCombinedParser<HuaweiParser, HuaweiLexer> {
  private final HuaweiConfigurationNormalizer.Result _normalized;

  public HuaweiCombinedParser(String input, GrammarSettings settings) {
    this(HuaweiConfigurationNormalizer.normalize(input), settings);
  }

  private HuaweiCombinedParser(
      HuaweiConfigurationNormalizer.Result normalized, GrammarSettings settings) {
    super(
        HuaweiParser.class,
        HuaweiLexer.class,
        normalized.text(),
        settings,
        new BatfishANTLRErrorStrategy.BatfishANTLRErrorStrategyFactory(HuaweiLexer.NEWLINE, "\n"),
        BatfishLexerRecoveryStrategy.WHITESPACE_AND_NEWLINES);
    _normalized = normalized;
  }

  public int originalLine(int line) {
    return _normalized.originalLine(line);
  }

  @Override
  public HuaweiParser.Huawei_configurationContext parse() {
    return _parser.huawei_configuration();
  }
}
