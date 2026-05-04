use odbpp_exporter::{export_semantic_json_file, ExportOptions, RUST_EXPORTER_VERSION};
use std::env;
use std::path::PathBuf;
use std::process;

#[derive(Debug, Clone)]
struct CliOptions {
    input: PathBuf,
    output: PathBuf,
    step: Option<String>,
    product_name: Option<String>,
}

fn main() {
    match run() {
        Ok(()) => {}
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "-h" || arg == "--help") {
        println!("{}", help_text());
        return Ok(());
    }
    if args.iter().any(|arg| arg == "--version") {
        println!("{RUST_EXPORTER_VERSION}");
        return Ok(());
    }
    let options = parse_args(args)?;
    let summary = export_semantic_json_file(
        &options.input,
        &options.output,
        &ExportOptions {
            step_name: options.step,
            product_name: options.product_name,
        },
    )
    .map_err(|error| error.to_string())?;
    println!(
        "ODB++ written to {} (step={}, units={}, layers={}, features={}, components={}, packages={}, nets={})",
        summary.root.display(),
        summary.step_name,
        summary.units,
        summary.layer_count,
        summary.feature_count,
        summary.component_count,
        summary.package_count,
        summary.net_count
    );
    Ok(())
}

fn parse_args(args: Vec<String>) -> Result<CliOptions, String> {
    if args.is_empty() {
        return Err(help_text());
    }

    let mut input = None;
    let mut output = None;
    let mut step = None;
    let mut product_name = None;

    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--output" | "-o" => {
                index += 1;
                output = Some(PathBuf::from(value_at(&args, index, "--output")?));
            }
            "--step" => {
                index += 1;
                step = Some(value_at(&args, index, "--step")?);
            }
            "--product-name" => {
                index += 1;
                product_name = Some(value_at(&args, index, "--product-name")?);
            }
            value if value.starts_with('-') => {
                return Err(format!("unknown option {value:?}\n\n{}", help_text()));
            }
            value => {
                if input.is_some() {
                    return Err(format!("unexpected positional argument {value:?}"));
                }
                input = Some(PathBuf::from(value));
            }
        }
        index += 1;
    }

    let Some(input) = input else {
        return Err(format!(
            "missing SemanticBoard JSON path\n\n{}",
            help_text()
        ));
    };
    let Some(output) = output else {
        return Err(format!("missing --output path\n\n{}", help_text()));
    };

    Ok(CliOptions {
        input,
        output,
        step,
        product_name,
    })
}

fn value_at(args: &[String], index: usize, option: &str) -> Result<String, String> {
    args.get(index)
        .cloned()
        .ok_or_else(|| format!("{option} requires a value"))
}

fn help_text() -> String {
    "Usage: odbpp_exporter <semantic-board.json> -o <odbpp-output-dir>\n\
     \n\
     Options:\n\
       -o, --output PATH       Write the ODB++ directory package to PATH.\n\
       --step STEP             ODB++ step directory name. Default: pcb.\n\
       --product-name NAME     ODB++ product/job name metadata. Default: aurora_semantic.\n\
       --version               Print exporter version."
        .to_string()
}
