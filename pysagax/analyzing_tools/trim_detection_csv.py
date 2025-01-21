"""
This script removes lines from the input .csv file 
where the detection.meanAzimuthCompensated field doesn't change (compared to the previous row)
"""
import click
import pandas as pd


@click.command()
@click.argument('source', type=click.STRING)
@click.argument('output', type=click.Path(), required=False)
@click.option('--trim-by', help='Keep rows where this field changes', default="detection.meanAzimuthCompensated")
def main(source, output, trim_by):
    """
    This script removes lines from the input .csv file where the field
    defined by --trim-by option (default: detection.meanAzimuthCompensated) doesn't change  (compared to the previous row).

    SOURCE source .csv file
    OUTPUT is the output CSV file (not required).
    """
    if not output:
        output = ".".join(source.split(".")[:-1]) + "_trimmed.csv"
        
    
    df = pd.read_csv(source)

    keep_rows = df[trim_by].diff()
    keep_rows[0] = 1
    df = df[keep_rows != 0]

    df.to_csv(output)


if __name__ == "__main__":
    main()