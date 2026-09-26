import type { components } from "../../api/schema";

type Capability = components["schemas"]["Capability"];
type JsonValue = components["schemas"]["JsonValue"];

export type ExpertDraft = {
  fields: Record<string, string>;
  optionsText: string;
};

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function schemaFields(capability: Capability) {
  return Object.entries(object(capability.parameters_schema.properties)).filter(
    ([key]) => key !== "options",
  );
}

export function defaultExpertDraft(capability: Capability): ExpertDraft {
  const fields: Record<string, string> = {};
  for (const [name, schema] of schemaFields(capability)) {
    const value = capability.defaults[name] ?? object(schema).default;
    if (value !== undefined && value !== null)
      fields[name] =
        typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }
  return {
    fields,
    optionsText: JSON.stringify(capability.defaults.options ?? {}, null, 2),
  };
}

export function buildExpertParameters(
  capability: Capability,
  draft: ExpertDraft,
): Record<string, JsonValue> {
  const result: Record<string, JsonValue> = {};
  const required = new Set(capability.required_fields);
  for (const [name, rawSchema] of schemaFields(capability)) {
    const raw = draft.fields[name]?.trim() ?? "";
    if (!raw) {
      if (required.has(name)) throw new Error(`${name} 为必填参数。`);
      continue;
    }
    const schema = object(rawSchema);
    if (
      schema.type === "string" ||
      (Array.isArray(schema.enum) &&
        schema.enum.every((v) => typeof v === "string"))
    ) {
      result[name] = raw;
      continue;
    }
    try {
      result[name] = JSON.parse(raw) as JsonValue;
    } catch {
      throw new Error(`${name} JSON 格式错误。`);
    }
  }
  let options: unknown;
  try {
    options = JSON.parse(draft.optionsText);
  } catch {
    throw new Error("options JSON 格式错误，输入内容已保留。");
  }
  if (!options || typeof options !== "object" || Array.isArray(options))
    throw new Error("options JSON 必须是对象。");
  result.options = options as JsonValue;
  return result;
}

export function effectiveExpertParameters(
  capability: Capability,
  draft: ExpertDraft,
): Record<string, JsonValue> {
  const requested = buildExpertParameters(capability, draft);
  return {
    ...capability.defaults,
    ...requested,
    options: {
      ...object(capability.defaults.options),
      ...object(requested.options),
    } as JsonValue,
  };
}
