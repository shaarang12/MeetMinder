from flask import Flask, render_template, request, redirect, url_for
import os
import boto3
import botocore
import tempfile
from moviepy.editor import VideoFileClip
import replicate

app = Flask(__name__)

# Set the Replicate API token
os.environ["REPLICATE_API_TOKEN"] = "r8_8G0tzSLsiHWsDoV1fZT8TMwbDBWYHu43qoPj1"

# Configure S3 client
s3 = boto3.client('s3')

# Define a function to upload audio to S3
def upload_audio_to_s3(audio_file, bucket_name, object_name):
    try:
        s3.upload_file(audio_file, bucket_name, object_name)
    except botocore.exceptions.NoCredentialsError:
        print("AWS credentials not available")

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return redirect(url_for('index'))

    video = request.files['video']
    # Save the video file to a location or process it as needed

    # Pass the video file name to the next page
    return redirect(url_for('play_video', filename=video.filename))


@app.route('/play/<filename>')
def play_video(filename):
    return render_template('result.html', filename=filename)

@app.route('/process', methods=['POST'])
def process():
    if 'video' not in request.files:
        return redirect(request.url)

    video = request.files['video']


    if video.filename == '':
        return redirect(request.url)

    # Retrieve the 'num-speakers' input from the form
    num_speakers = int(request.form['num-speakers'])

    # Create a temporary directory to save the uploaded video and extracted audio
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, 'uploaded_video.mp4')
        audio_path = os.path.join(temp_dir, 'extracted_audio.mp3')

        # Save the uploaded video
        video.save(video_path)

        # Extract audio from the video
        video_clip = VideoFileClip(video_path)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(audio_path)

        # Close the video and audio clips to release resources
        video_clip.close()
        audio_clip.close()

        # Upload the extracted audio to S3
        bucket_name = 'meetminder-2023'
        object_name = 'audio/extracted_audio.mp3'
        upload_audio_to_s3(audio_path, bucket_name, object_name)

        # Run the Replicate code with the extracted audio
        output = replicate.run(
            "thomasmol/whisper-diarization:249170b5f45bb1e0aa68440f1f28ef25f5ee50a882af365555068f1f61ae791b",
            input={
                "file": "https://meetminder-2023.s3.amazonaws.com/audio/extracted_audio.mp3",
                "prompt": "",
                "file_url": "",
                "num_speakers": num_speakers,
                "group_segments": True,
                "offset_seconds": 0
            }
        )
        # path = "C:\Users\shaar\IdeaProjects\MM\"
        # path += video.filename
        #
        # return render_template('result.html', video_path=path)
    # #OUTPUT FOR START TIME - END TIME - SPEAKER - TEXT
    reformatted_output = []
    for segment in output["segments"]:
        start_time = segment["start"]
        end_time = segment["end"]
        speaker = segment["speaker"]
        text = segment["text"]
        reformatted_output.append([start_time, end_time, speaker, text])
    print(output)
    TEXT = ""
    for segment in output["segments"]:
        TEXT += segment["text"]


    output = replicate.run(
        "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
        input={
            "debug": False,
            "top_k": 50,
            "top_p": 1,
            "prompt": "Summarize the given meeting transcription text that appears after the period and give roughly 300 word concise paragraph on what it is about. " +TEXT,
            "temperature": 0.5,
            "system_prompt": "You are a helpful, honest assistant. Always answer as helpfully as possible, while being safe.\n\nYour job is to summarize the given transcription text, without losing its meaning.",
            "max_new_tokens": 500,
            "min_new_tokens": -1
        }
    )
    # Convert the generator to a list
    output_list = list(output)

    # Remove empty strings from the list
    output_list = [token.strip() for token in output_list if token.strip()]

    #  Join the list to get the final summary text
    summary_text = ' '.join(output_list)
    # summary = ""
    # for text in output:
    #     summary += text


    # print(reformatted_output)
    return render_template('result.html', reformatted_output=reformatted_output, filename=video.filename, summary=summary_text)
    #OUTPUT FOR SPEAKER_00 and SPEAKER_01
    # SPEAKER_00 = ""
    # SPEAKER_01 = ""
    # for segment in output["segments"]:
    #     if(segment["speaker"] == 'SPEAKER_00'):
    #         SPEAKER_00 += segment["text"]
    #     else:
    #         SPEAKER_01 += segment["text"]
    #
    #
    # return render_template('result.html', SPEAKER_00=SPEAKER_00, SPEAKER_01=SPEAKER_01)


    # return render_template('result.html', TEXT = TEXT)


if __name__ == '__main__':
    app.run(debug=True)
