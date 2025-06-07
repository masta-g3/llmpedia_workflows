import os
import argparse
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from PIL import Image  # Required for saving images, marker returns PIL.Image objects


def convert_pdf_to_markdown_local(pdf_path: str):
    """Convert a local PDF file to markdown and extract images using the marker library."""
    converter = PdfConverter(artifact_dict=create_model_dict())
    try:
        rendered_output = converter(pdf_path)
        markdown_text, _, images = text_from_rendered(
            rendered_output
        )  # images is a dict[str, PIL.Image]
        return markdown_text, images
    except Exception as e:
        print(f"Error converting PDF to markdown: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Convert a PDF file to Markdown format and save images."
    )
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file.")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found at {args.pdf_path}")
        return

    print(f"Processing PDF: {args.pdf_path}")
    markdown_text, images = convert_pdf_to_markdown_local(args.pdf_path)

    if markdown_text is None:
        print("Failed to convert PDF to markdown.")
        return

    base_path = os.path.splitext(args.pdf_path)[0]
    markdown_output_path = base_path + ".md"
    images_output_dir = base_path + "_images"

    # Save markdown file
    try:
        with open(markdown_output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        print(f"Markdown content saved to: {markdown_output_path}")
    except IOError as e:
        print(f"Error saving markdown file: {e}")
        return

    # Save images
    if images:
        if not os.path.exists(images_output_dir):
            os.makedirs(images_output_dir)

        print(f"Saving {len(images)} images to: {images_output_dir}")
        for img_name, img_obj in images.items():
            try:
                # Ensure img_name has a valid extension, default to .png if not
                if not os.path.splitext(img_name)[1]:
                    img_name_ext = img_name + ".png"
                else:
                    img_name_ext = img_name

                img_save_path = os.path.join(images_output_dir, img_name_ext)
                img_obj.save(
                    img_save_path
                )  # marker usually returns PNG, format can be inferred or explicitly set
                print(f"  Saved image: {img_name_ext}")
            except Exception as e:
                print(f"  Error saving image {img_name}: {e}")
    else:
        print("No images found or extracted.")

    print("Conversion complete.")


if __name__ == "__main__":
    main()
