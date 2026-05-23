from typing import Annotated, List, Any, Optional, Dict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)

from pydantic import BaseModel, Field

from utils.constants import (
    WORKER_LLM_CONFIG,
    EVALUATOR_LLM_CONFIG,
)

from utils.env_helper import load_environment
from utils.sidekick_tools import (
    playwright_tools,
    other_tools,
)
from utils.persistence import (
    get_persistence_memory_type,
)

from datetime import datetime

import uuid
import asyncio


load_environment()


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


class EvaluatorOutput(BaseModel):

    feedback: str = Field(
        description="Feedback on the assistant response"
    )

    success_criteria_met: bool = Field(
        description="Whether success criteria were met"
    )

    user_input_needed: bool = Field(
        description="Whether more user clarification is needed"
    )


class Sidekick:

    def __init__(self):

        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None

        self.tools = None

        self.graph = None

        self.browser = None
        self.playwright = None

        self.sidekick_id = str(
            uuid.uuid4()
        )

        self.memory = None

    async def setup(self):

        self.memory = await get_persistence_memory_type()

        self.tools, self.browser, self.playwright = (
            await playwright_tools()
        )

        self.tools += await other_tools()

        worker_llm = ChatGoogleGenerativeAI(
            **WORKER_LLM_CONFIG
        )

        self.worker_llm_with_tools = (
            worker_llm.bind_tools(self.tools)
        )

        evaluator_llm = ChatGoogleGenerativeAI(
            **EVALUATOR_LLM_CONFIG
        )

        self.evaluator_llm_with_output = (
            evaluator_llm.with_structured_output(
                EvaluatorOutput
            )
        )

        await self.build_graph()

    def worker(
        self,
        state: State,
    ) -> Dict[str, Any]:

        system_message = f"""
You are a helpful AI assistant that can use tools.

You continue working until:
- success criteria are met
- OR you genuinely need clarification from the user

You can:
- browse the web
- use tools
- execute Python
- write files

Current datetime:
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Success criteria:
{state["success_criteria"]}

If you need clarification, clearly ask a question.

Otherwise provide the final answer directly.
"""

        if state.get("feedback_on_work"):

            system_message += f"""

Previous attempt feedback:
{state["feedback_on_work"]}

Use this feedback to improve your next response.
"""

        messages = state["messages"]

        found_system_message = False

        for message in messages:

            if isinstance(message, SystemMessage):

                message.content = system_message

                found_system_message = True

        if not found_system_message:

            messages = [
                SystemMessage(
                    content=system_message
                )
            ] + messages

        response = self.worker_llm_with_tools.invoke(
            messages
        )

        return {
            "messages": [response]
        }

    def worker_router(
        self,
        state: State,
    ) -> str:

        last_message = state["messages"][-1]

        if (
            hasattr(last_message, "tool_calls")
            and last_message.tool_calls
        ):
            return "tools"

        return "evaluator"

    def format_conversation(
        self,
        messages: List[Any],
    ) -> str:

        conversation = (
            "Conversation history:\n\n"
        )

        for message in messages:

            if isinstance(
                message,
                HumanMessage,
            ):
                conversation += (
                    f"User: {message.content}\n"
                )

            elif isinstance(
                message,
                AIMessage,
            ):

                text = (
                    message.content
                    or "[Tool Usage]"
                )

                conversation += (
                    f"Assistant: {text}\n"
                )

        return conversation

    def evaluator(
        self,
        state: State,
    ) -> Dict[str, Any]:

        last_response = (
            state["messages"][-1].content
        )

        system_message = """
You are an evaluator.

Determine:
- whether success criteria are met
- whether clarification is needed
- provide concise feedback
"""

        user_message = f"""
Conversation:
{self.format_conversation(state["messages"])}

Success Criteria:
{state["success_criteria"]}

Assistant Final Response:
{last_response}
"""

        if state.get("feedback_on_work"):

            user_message += f"""

Previous evaluator feedback:
{state["feedback_on_work"]}
"""

        evaluator_messages = [
            SystemMessage(
                content=system_message
            ),
            HumanMessage(
                content=user_message
            ),
        ]

        eval_result = (
            self.evaluator_llm_with_output.invoke(
                evaluator_messages
            )
        )

        return {
            "messages": [
                AIMessage(
                    content=f"Evaluator Feedback: {eval_result.feedback}"
                )
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }

    def route_based_on_evaluation(
        self,
        state: State,
    ) -> str:

        if (
            state["success_criteria_met"]
            or state["user_input_needed"]
        ):
            return "END"

        return "worker"

    async def build_graph(self):

        graph_builder = StateGraph(
            State
        )

        graph_builder.add_node(
            "worker",
            self.worker,
        )

        graph_builder.add_node(
            "tools",
            ToolNode(
                tools=self.tools
            ),
        )

        graph_builder.add_node(
            "evaluator",
            self.evaluator,
        )

        graph_builder.add_conditional_edges(
            "worker",
            self.worker_router,
            {
                "tools": "tools",
                "evaluator": "evaluator",
            },
        )

        graph_builder.add_edge(
            "tools",
            "worker",
        )

        graph_builder.add_conditional_edges(
            "evaluator",
            self.route_based_on_evaluation,
            {
                "worker": "worker",
                "END": END,
            },
        )

        graph_builder.add_edge(
            START,
            "worker",
        )

        self.graph = graph_builder.compile(
            checkpointer=self.memory
        )

    async def run_superstep(
        self,
        message,
        success_criteria,
        history,
    ):

        config = {
            "configurable": {
                "thread_id": self.sidekick_id
            }
        }

        state = {
            "messages": [
                HumanMessage(
                    content=message
                )
            ],
            "success_criteria": (
                success_criteria
                or "The answer should be clear and accurate"
            ),
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }

        result = await self.graph.ainvoke(
            state,
            config=config,
        )

        final_response = (
            result["messages"][-2].content
        )

        feedback = (
            result["messages"][-1].content
        )

        history = history or []

        history.append(
            {
                "role": "user",
                "content": message,
            }
        )

        history.append(
            {
                "role": "assistant",
                "content": final_response,
            }
        )

        history.append(
            {
                "role": "assistant",
                "content": feedback,
            }
        )

        return history

    def cleanup(self):

        async def _cleanup():

            if self.browser:
                await self.browser.close()

            if self.playwright:
                await self.playwright.stop()

        try:

            loop = asyncio.get_running_loop()

            loop.create_task(
                _cleanup()
            )

        except RuntimeError:

            asyncio.run(
                _cleanup()
            )