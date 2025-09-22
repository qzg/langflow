from lfx.base.io.chat import ChatComponent
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class UIBuilder(ChatComponent):
    """UI Builder component (stub).

    Provides visible input and output handles and a minimal pass-through implementation.
    The front-end shows an 'Edit UI' button for this node which opens the Builder dialog.
    """

    display_name = "UI Builder"
    description = "Agent-driven UI Builder that scaffolds and iterates on a web UI connected to flows."
    icon = "Wrench"
    name = "UIBuilder"

    # Minimal handles to satisfy initial acceptance: one input, one output
    inputs = [
        MessageTextInput(
            name="ui_input",
            display_name="UI Input",
            info="Input to UI Builder (optional).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="UI Output", name="ui_output", method="pass_through"),
    ]

    def pass_through(self) -> Message:
        """Return the input message or a placeholder message if none provided."""
        if getattr(self, "ui_input", None):
            return Message(text=self.ui_input)
        return Message(text="UI Builder output (stub)")
