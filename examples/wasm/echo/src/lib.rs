// NOTE: This is a minimal illustrative example; versions of wit-bindgen and module paths may differ.

wit_bindgen::generate!({
    path: "echo.wit",
    world: "echo",
});

use exports::demo::echo::echo::Guest;

struct Echo;

impl Guest for Echo {
    fn process(input: String) -> String {
        input
    }
}

export!(Echo);
