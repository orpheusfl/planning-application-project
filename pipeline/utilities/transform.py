

from datetime import datetime


class Application:

    def __init__(self,
                 application_number: str,
                 application_type: str,
                 address: str,
                 postcode: str,
                 lat: float,
                 long: float,
                 validation_date: str,
                 status: str,
                 ai_summary: str,
                 public_interest_score: int,
                 pdfs: list[dict]) -> None:
        """Output:
        {
            application_number: str
            application_type:
            address: str
            postcode: str
            lat (maybe):
            long (maybe):
            validation_date: str
            status: str
            ai_summary: str
            public_interest_score: int
            pdfs: list[dict]
        }"""
        self.application_number = application_number
        self.application_type = application_type
        self.address = self.get_postcode_and_address_from_address(address)[
            'address']
        self.postcode = self.get_postcode_and_address_from_address(address)[
            'postcode']
        self.lat = self.get_lat_and_long_from_address(address)['lat']
        self.long = self.get_lat_and_long_from_address(address)['long']
        self.validation_date = self.parse_validation_date_to_datetime(
            validation_date)
        self.status = status
        self.ai_summary = self.pdf_urls_to_analysis(pdfs)['ai_summary']
        self.public_interest_score = self.pdf_urls_to_analysis(pdfs)[
            'public_interest_score']
        self.pdfs = self.store_pdf_data(pdfs)

    def extract_pdf_from_url(url: str) -> bytes:
        """Takes a url and extracts a pdf file from it"""
        pass

    def store_pdf_data(pdf: list[dict]) -> list[dict]:
        """Takes a list of urls and document types and extracts the pdf files from them,
        returning a dict with the document type and the pdf data as bytes."""
        pass

    def extract_text_from_pdf(pdf: bytes) -> str:
        """Takes a pdf file and extracts all main body text from it"""
        pass

    def clean_pdf_text(text: str) -> str:
        """Cleans the text extracted from the pdf, removing any irrelevant information."""
        pass

    def build_llm_analysis_prompt(text: str) -> str:
        """Uses the pdf text to build a query, ready for an LMM prompt"""
        pass

    def analyse_pdf_text(prompt: str) -> dict:
        """Uses LLM API to analyse prompt and return structured output.

        {ai_summary: str
        public_interest_score: int}"""
        pass

    def pdf_urls_to_analysis(pdfs: list[dict]) -> dict:
        """Takes a list of pdf urls and document types, extracts the pdfs, extracts the text from the pdfs,
        cleans the text, builds a prompt for the LLM, and returns the analysis from the LLM."""
        pass

    def get_postcode_and_address_from_address(address: str) -> dict:
        """Extracts the postcode from the address.
            Returns the address and the postcode as separate fields.
            strip and capitalise postcode.

            Example input: 	36A Grove Road, London, E3 5AX

            Example output: {address: "36A Grove Road, London", postcode: "E35AX"}"""
        pass

    def get_lat_and_long_from_address(address: str) -> dict:
        """Takes an address and returns the lat and long coordinates as a dict.
            Uses a geocoding API to get the coordinates."""
        pass

    def parse_validation_date_to_datetime(validation_date: str) -> datetime:
        """Takes the validation date as a string and parses it to a datetime object.
        Example input date format: Fri 20 Mar 2026"""
        pass
