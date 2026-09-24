package org.batfish.vendor.huawei.representation;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.batfish.datamodel.bgp.community.ExtendedCommunity;
import org.batfish.datamodel.bgp.community.StandardCommunity;

public final class HuaweiCommunity {
  public static StandardCommunity parse(String text) {
    return switch (text) {
      case "internet" -> StandardCommunity.of(0);
      case "no-export" -> StandardCommunity.of(0xFFFFFF01L);
      case "no-advertise" -> StandardCommunity.of(0xFFFFFF02L);
      case "no-export-subconfed" -> StandardCommunity.of(0xFFFFFF03L);
      default ->
          text.contains(":")
              ? StandardCommunity.parse(text)
              : StandardCommunity.of(Long.parseLong(text));
    };
  }

  /** Shared validation and conversion of basic extended-community filter values. */
  public static List<ExtendedCommunity> parseExtendedValues(List<String> values) {
    List<ExtendedCommunity> communities = new ArrayList<>();
    String type = "rt";
    boolean needsValue = true;
    for (String value : values) {
      if (Set.of("rt", "soo", "color").contains(value)) {
        type = value;
        needsValue = true;
        continue;
      }
      if (type.equals("color")) {
        String[] color = value.split(":", -1);
        if (color.length > 2) {
          throw new IllegalArgumentException("Invalid color");
        }
        long flags = color.length == 2 ? Long.parseLong(color[0], 16) : 0;
        long number = Long.parseLong(color[color.length - 1]);
        if (flags < 0 || flags > 0xFFFF || number < 0 || number > 0xFFFFFFFFL) {
          throw new IllegalArgumentException("Invalid color");
        }
        communities.add(ExtendedCommunity.opaque(true, 11, (flags << 32) | number));
      } else {
        communities.add(
            ExtendedCommunity.parse((type.equals("soo") ? "origin:" : "target:") + value));
      }
      needsValue = false;
    }
    if (needsValue) {
      throw new IllegalArgumentException("Missing extended community");
    }
    return communities;
  }

  private HuaweiCommunity() {}
}
