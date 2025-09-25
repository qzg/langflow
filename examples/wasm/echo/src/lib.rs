// NOTE: This is a minimal illustrative example; versions of wit-bindgen and module paths may differ.

#[allow(warnings)]
mod bindings {
    wit_bindgen::generate!({
        path: "echo.wit",
        world: "echo",
    });
}

// Prefer referencing generated items through the `bindings` module to avoid
// ambiguity between local modules and external crates.
use bindings::Guest;

struct Echo;

impl Guest for Echo {
    fn process(input: String) -> String {
        input
    }
}

bindings::export!(Echo with_types_in bindings);
