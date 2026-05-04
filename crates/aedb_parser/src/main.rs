use aurora_aedb_native::{
    auroradb::compare_def_to_auroradb, build_payload, roundtrip_def, BuildPayloadOptions,
    BACKEND_CLI, RUST_PARSER_VERSION,
};
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Command {
    Parse,
    Roundtrip,
    CompareAuroraDb,
}

#[derive(Debug, Clone)]
struct CliOptions {
    command: Command,
    source: PathBuf,
    output: Option<PathBuf>,
    auroradb_root: Option<PathBuf>,
    include_details: bool,
    indent: Option<usize>,
    project_version: String,
    parser_version: String,
    schema_version: String,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "-h" || arg == "--help") {
        println!("{}", help_text());
        return Ok(());
    }
    let options = parse_args(args)?;
    match options.command {
        Command::Parse => run_parse(options),
        Command::Roundtrip => run_roundtrip(options),
        Command::CompareAuroraDb => run_compare_auroradb(options),
    }
}

fn run_parse(options: CliOptions) -> Result<(), String> {
    let payload = build_payload(&BuildPayloadOptions {
        source: options.source,
        include_details: options.include_details,
        project_version: options.project_version,
        parser_version: options.parser_version,
        schema_version: options.schema_version,
        backend: BACKEND_CLI.to_string(),
    })?;
    let json = if options.indent.is_some() {
        serde_json::to_string_pretty(&payload).map_err(|error| error.to_string())?
    } else {
        serde_json::to_string(&payload).map_err(|error| error.to_string())?
    };
    if let Some(output) = options.output {
        if let Some(parent) = output.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).map_err(|error| error.to_string())?;
            }
        }
        fs::write(&output, json).map_err(|error| error.to_string())?;
    } else {
        println!("{json}");
    }
    Ok(())
}

fn run_roundtrip(options: CliOptions) -> Result<(), String> {
    let Some(output) = options.output else {
        return Err("roundtrip requires -o/--output".to_string());
    };
    roundtrip_def(options.source, output)
}

fn run_compare_auroradb(options: CliOptions) -> Result<(), String> {
    let Some(auroradb_root) = options.auroradb_root else {
        return Err("compare-auroradb requires --auroradb PATH".to_string());
    };
    let comparison = compare_def_to_auroradb(&options.source, &auroradb_root)?;
    let json = if options.indent.is_some() {
        serde_json::to_string_pretty(&comparison).map_err(|error| error.to_string())?
    } else {
        serde_json::to_string(&comparison).map_err(|error| error.to_string())?
    };
    if let Some(output) = options.output {
        if let Some(parent) = output.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).map_err(|error| error.to_string())?;
            }
        }
        fs::write(&output, json).map_err(|error| error.to_string())?;
    } else {
        println!("{json}");
    }
    Ok(())
}

fn parse_args(args: Vec<String>) -> Result<CliOptions, String> {
    if args.is_empty() {
        return Err(help_text());
    }

    let mut command = Command::Parse;
    let mut start_index = 0;
    match args[0].as_str() {
        "parse" => {
            command = Command::Parse;
            start_index = 1;
        }
        "roundtrip" | "write-def" => {
            command = Command::Roundtrip;
            start_index = 1;
        }
        "compare-auroradb" => {
            command = Command::CompareAuroraDb;
            start_index = 1;
        }
        _ => {}
    }

    let mut source = None;
    let mut output = None;
    let mut auroradb_root = None;
    let mut include_details = true;
    let mut indent = Some(2);
    let mut project_version = "unknown".to_string();
    let mut parser_version = RUST_PARSER_VERSION.to_string();
    let mut schema_version = "0.4.0".to_string();

    let mut index = start_index;
    while index < args.len() {
        match args[index].as_str() {
            "--output" | "-o" => {
                index += 1;
                output = Some(PathBuf::from(value_at(&args, index, "--output")?));
            }
            "--auroradb" => {
                index += 1;
                auroradb_root = Some(PathBuf::from(value_at(&args, index, "--auroradb")?));
            }
            "--summary-only" => include_details = false,
            "--indent" => {
                index += 1;
                let value = value_at(&args, index, "--indent")?;
                indent = Some(
                    value
                        .parse::<usize>()
                        .map_err(|_| format!("invalid --indent value {value:?}"))?,
                );
            }
            "--compact" => indent = None,
            "--project-version" => {
                index += 1;
                project_version = value_at(&args, index, "--project-version")?;
            }
            "--parser-version" => {
                index += 1;
                parser_version = value_at(&args, index, "--parser-version")?;
            }
            "--schema-version" => {
                index += 1;
                schema_version = value_at(&args, index, "--schema-version")?;
            }
            value if value.starts_with('-') => {
                return Err(format!("unknown option {value:?}\n\n{}", help_text()));
            }
            value => {
                if source.is_some() {
                    return Err(format!("unexpected positional argument {value:?}"));
                }
                source = Some(PathBuf::from(value));
            }
        }
        index += 1;
    }

    let Some(source) = source else {
        return Err(format!("missing source path\n\n{}", help_text()));
    };

    Ok(CliOptions {
        command,
        source,
        output,
        auroradb_root,
        include_details,
        indent,
        project_version,
        parser_version,
        schema_version,
    })
}

fn value_at(args: &[String], index: usize, option: &str) -> Result<String, String> {
    args.get(index)
        .cloned()
        .ok_or_else(|| format!("{option} requires a value"))
}

fn help_text() -> String {
    "Usage:\n\
       aedb_parser parse <board.def> [--summary-only] [-o OUTPUT]\n\
       aedb_parser roundtrip <board.def> -o OUTPUT.def\n\
       aedb_parser compare-auroradb <board.def> --auroradb AURORADB_DIR [-o OUTPUT]\n\
     \n\
     Options:\n\
       --summary-only           Count DEF records and skip detail arrays.\n\
       -o, --output PATH        Write JSON or roundtrip DEF output to a file.\n\
       --auroradb PATH          Standard AuroraDB directory for compare-auroradb.\n\
       --indent N               Pretty-print JSON with N spaces. Default: 2.\n\
       --compact                Emit compact JSON.\n\
       --project-version VALUE  Metadata project version injected by Aurora Translator.\n\
       --parser-version VALUE   AEDB DEF parser version injected by Aurora Translator.\n\
       --schema-version VALUE   AEDB DEF JSON schema version injected by Aurora Translator."
        .to_string()
}
