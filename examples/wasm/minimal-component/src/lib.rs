// Minimal Rust skeleton for the `langflow:minimal` WIT world.
// Note: Depending on your wit-bindgen/cargo-component versions, you may need to adjust the macros.

wit_bindgen::generate!({
    path: "wit",
    world: "component"
});

struct Component;

impl exports::langflow::minimal::component::Guest for Component {
    fn process(input: String) -> String {
        format!("echo: {}", input)
    }
}

// Some toolchains expose an `export!` macro. If needed in your environment, uncomment:
// wit_bindgen::export!(Component);