#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import os
import sys
import aiohttp
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.processors.metrics.sentry import SentryMetrics
from pipecat.transcriptions.language import Language
from pipecat.services.gemini_multimodal_live.gemini import (
    GeminiMultimodalLiveLLMService,

)

from pipecat.adapters.schemas.tools_schema import ToolsSchema
import tools
from prompt import PROMPT

load_dotenv(override=True)
import sentry_sdk

sentry_sdk.init(
    dsn="https://9c02693b0e523afa657bc73ec4355eb7@o4509937834328064.ingest.de.sentry.io/4509937839571024",
    traces_sample_rate=1.0,

)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def run_bot(
    websocket_client,
    stream_sid: str,
    call_sid: str,
    language:str
):
    serializer = ExotelFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
            
        ),
    )

    tools_schema = ToolsSchema(
            standard_tools=[
                tools.fs_get_order_details,
                tools.fs_get_status,
                tools.fs_cancel,
                tools.fs_change_address,
            ]
        )
    
    
    llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            model="models/gemini-2.0-flash-live-001",
            
            # params=InputParams(modalities=GeminiMultimodalModalities.TEXT),
            # system_instruction=EN_PROMPT if language == "en" else HI_PROMPT ,
            system_instruction=PROMPT  ,
            tools=tools_schema,
            voice_id="Zephyr",
            metrics = SentryMetrics(),
        )

    # session_properties = SessionProperties(
    #     input_audio_transcription=InputAudioTranscription(),
    #     # modalities=["audio"],
    #     turn_detection=SemanticTurnDetection(),
      
    #     # instructions=EN_PROMPT if language == "en" else HI_PROMPT ,
    #     instructions=EN_PROMPT ,
    # )
     
     
    # llm = OpenAIRealtimeBetaLLMService(
    #     api_key=os.getenv("OPENAI_API_KEY"),
    #     session_properties=session_properties,
    #     start_audio_paused=False,
    #     model="gpt-realtime-2025-08-28"
    #     # model="gpt-4o-mini-realtime-preview-2024-12-17"
    # )

        # register handlers with the LLM service
    llm.register_function("get_order_details", tools._handle_get_order)
    llm.register_function("get_order_status", tools._handle_get_status)
    llm.register_function("cancel_order", tools._handle_cancel)
    llm.register_function("change_delivery_address", tools._handle_change_address)


    session = aiohttp.ClientSession()

    tts = SarvamTTSService(
            api_key=os.getenv("SARVAM_API_KEY"),
            aiohttp_session=session,
            params=SarvamTTSService.InputParams(language=Language.HI if language =="hi" else Language.EN),
            sample_rate=8000,
            voice_id="manisha"
        )

   
     # register handlers with the LLM service
    
    
     # register handlers with the LLM service
    llm.register_function("get_order_details", tools._handle_get_order)
    llm.register_function("get_order_status", tools._handle_get_status)
    llm.register_function("cancel_order", tools._handle_cancel)
    llm.register_function("change_delivery_address", tools._handle_change_address)
    
    messages = [
            {
                "role": "user",
                "content": 'Start by saying "Hello, and give short intro ',
            },
        ]
    
      # For Gemini
    context = OpenAILLMContext(messages)
    # context = OpenAILLMContext(messages,tools= tools_schema)
    context_aggregator = llm.create_context_aggregator(context)

    # rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
    

    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            context_aggregator.user(),
            llm,  # LLM
            # tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation.
      logger.info(f"Client connected")
      await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)
