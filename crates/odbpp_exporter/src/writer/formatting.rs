use std::collections::HashSet;

pub(super) fn odb_net_name(value: &str) -> String {
    let text = value.trim();
    if text.is_empty() {
        "UNNAMED_NET".to_string()
    } else {
        text.to_string()
    }
}

pub(super) fn odb_token(value: &str) -> String {
    let cleaned = value.replace(['"', '\''], "_");
    if cleaned.is_empty()
        || cleaned
            .chars()
            .any(|ch| ch.is_whitespace() || matches!(ch, ';' | ',' | '#'))
    {
        format!("\"{cleaned}\"")
    } else {
        cleaned
    }
}

pub(super) fn feature_id(id: &str, raw_id: Option<&str>) -> Option<String> {
    Some(legal_scalar(raw_id.unwrap_or(id)))
}

pub(super) fn legal_step_name(value: &str) -> String {
    legal_entity_name(value).to_ascii_lowercase()
}

pub(super) fn legal_entity_name(value: &str) -> String {
    let mut output = String::new();
    for ch in value.trim().chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '+' | '-' | '.') {
            output.push(ch.to_ascii_uppercase());
        } else if ch.is_whitespace() || matches!(ch, '/' | '\\' | ':' | '(' | ')' | '[' | ']') {
            output.push('_');
        }
    }
    while output.contains("__") {
        output = output.replace("__", "_");
    }
    let output = output.trim_matches('_').to_string();
    if output.is_empty() {
        "LAYER".to_string()
    } else {
        output
    }
}

pub(super) fn legal_symbol_name(value: &str) -> String {
    let text = value.trim();
    if text.starts_with('r')
        || text.starts_with("rect")
        || text.starts_with("oval")
        || text.starts_with('s')
    {
        return text.replace(' ', "_");
    }
    legal_scalar(text)
}

pub(super) fn legal_scalar(value: &str) -> String {
    let mut output = String::new();
    for ch in value.trim().chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '+' | '-' | '.' | '$') {
            output.push(ch);
        } else if ch.is_whitespace() || matches!(ch, '/' | '\\' | ':' | '(' | ')' | '[' | ']') {
            output.push('_');
        }
    }
    while output.contains("__") {
        output = output.replace("__", "_");
    }
    let output = output.trim_matches('_').to_string();
    if output.is_empty() {
        "UNKNOWN".to_string()
    } else {
        output
    }
}

pub(super) fn legal_component_name(value: &str) -> String {
    let result = legal_scalar(value);
    if result.is_empty() {
        "UNNAMED".to_string()
    } else {
        result
    }
}

pub(super) fn unique_name<'a>(base: String, existing: impl Iterator<Item = &'a str>) -> String {
    let used: HashSet<String> = existing.map(|value| value.to_ascii_lowercase()).collect();
    if !used.contains(&base.to_ascii_lowercase()) {
        return base;
    }
    for index in 2usize.. {
        let candidate = format!("{}_{}", base, index);
        if !used.contains(&candidate.to_ascii_lowercase()) {
            return candidate;
        }
    }
    unreachable!()
}

pub(super) fn fmt(value: f64) -> String {
    if !value.is_finite() {
        return "0".to_string();
    }
    let rounded = value.round();
    if (value - rounded).abs() < 1e-9 {
        return format!("{rounded:.0}");
    }
    let mut text = format!("{value:.12}");
    while text.contains('.') && text.ends_with('0') {
        text.pop();
    }
    if text.ends_with('.') {
        text.pop();
    }
    if text == "-0" {
        "0".to_string()
    } else {
        text
    }
}

pub(super) fn write_id(text: &mut String, id: &Option<String>) {
    if let Some(id) = id {
        text.push_str(";ID=");
        text.push_str(id);
    }
}

pub(super) fn write_kv(text: &mut String, key: &str, value: &str) {
    text.push_str(key);
    text.push('=');
    text.push_str(value);
    text.push('\n');
}
