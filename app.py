import gradio as gr

from sidekick import Sidekick


async def setup():
    """
    Initialize Sidekick instance.
    """

    sidekick = Sidekick()

    await sidekick.setup()

    return sidekick


def normalize_history(history):
    """
    Convert older tuple-style history into
    Gradio 6 message format if needed.
    """

    if history is None:
        return []

    normalized = []

    for item in history:

        # Already modern format
        if isinstance(item, dict):
            normalized.append(item)
            continue

        # Old tuple/list format
        if isinstance(item, (tuple, list)) and len(item) == 2:

            user_msg, assistant_msg = item

            normalized.append(
                {
                    "role": "user",
                    "content": str(user_msg),
                }
            )

            normalized.append(
                {
                    "role": "assistant",
                    "content": str(assistant_msg),
                }
            )

    return normalized


async def process_message(
    sidekick,
    message,
    success_criteria,
    history,
):
    """
    Process user request through Sidekick.
    """

    if sidekick is None:
        sidekick = Sidekick()
        await sidekick.setup()

    history = normalize_history(history)

    results = await sidekick.run_superstep(
        message=message,
        success_criteria=success_criteria,
        history=history,
    )

    results = normalize_history(results)

    return results, sidekick


async def reset():
    """
    Reset UI + Sidekick session.
    """

    new_sidekick = Sidekick()

    await new_sidekick.setup()

    return (
        "",
        "",
        [],
        new_sidekick,
    )


def free_resources(sidekick):
    """
    Cleanup resources safely.
    """

    print("Cleaning up resources...")

    try:
        if sidekick:
            sidekick.cleanup()

    except Exception as e:
        print(f"Cleanup error: {e}")


with gr.Blocks(
    title="The Sidekick"
) as ui:

    gr.Markdown(
        """
        # TheSidekick
        Personal AI Co-Worker
        """
    )

    sidekick = gr.State(
        value=None,
        delete_callback=free_resources,
    )

    chatbot = gr.Chatbot(
        label="TheSidekick",
        height=500,
    )

    with gr.Group():

        message = gr.Textbox(
            label="Request",
            placeholder="What do you want the Sidekick to do?",
            lines=3,
        )

        success_criteria = gr.Textbox(
            label="Success Criteria",
            placeholder="Describe what success looks like...",
            lines=2,
        )

    with gr.Row():

        reset_button = gr.Button(
            "Reset",
            variant="stop",
        )

        go_button = gr.Button(
            "Go!",
            variant="primary",
        )

    ui.load(
        fn=setup,
        inputs=[],
        outputs=[sidekick],
    )

    message.submit(
        fn=process_message,
        inputs=[
            sidekick,
            message,
            success_criteria,
            chatbot,
        ],
        outputs=[
            chatbot,
            sidekick,
        ],
    )

    success_criteria.submit(
        fn=process_message,
        inputs=[
            sidekick,
            message,
            success_criteria,
            chatbot,
        ],
        outputs=[
            chatbot,
            sidekick,
        ],
    )

    go_button.click(
        fn=process_message,
        inputs=[
            sidekick,
            message,
            success_criteria,
            chatbot,
        ],
        outputs=[
            chatbot,
            sidekick,
        ],
    )

    reset_button.click(
        fn=reset,
        inputs=[],
        outputs=[
            message,
            success_criteria,
            chatbot,
            sidekick,
        ],
    )


ui.launch(
    inbrowser=True,
)