"""
Utilities for public_data.
"""
import gzip
import json
import numpy as np
import pandas as pd


class PcbaJsonParser(object):
  """
  Parser for PubChemBioAssay JSON.

  Parameters
  ----------
  filename : str
      Filename.
  """
  def __init__(self, filename):
    if filename.endswith(".gz"):
      with gzip.open(filename) as f:
        self.tree = json.load(f)
    elif filename.endswith(".json"):
      with open(filename) as f:
        self.tree = json.load(f)
    else:
      raise ValueError("filename must be of type .json or .json.gz!")

    # move in to the assay description
    try:
        # FTP format
        self.root = self.tree['PC_AssaySubmit']['assay']['descr']
    except KeyError:
        # REST format
        # should just be one record per file
        assert len(self.tree['PC_AssayContainer']) == 1
        self.root = self.tree['PC_AssayContainer'][0]['assay']['descr']

  def get_name(self):
    """
    Get assay name.
    """
    return self.root['name']

  def get_aid(self):
    """
    Get assay AID.
    """
    return self.root["aid"]["id"]

  def get_activity_outcome_method(self):
    """
    Get activity outcome method.
    """
    #
    if "activity_outcome_method" in self.root:
      method = self.root["activity_outcome_method"]
      if "counter" in self.get_name().lower():
        method = "counterscreen"
      return method
    else:
      return None

  def get_description(self):
    """
    Get assay description.
    """
    if isinstance(self.root['description'], list):
      return '\n'.join(
        [line.strip() for line in self.root['description']])
    else:
      return self.root['description']

  def get_protocol(self):
    """
    Get assay protocol.
    """
    if isinstance(self.root['protocol'], list):
      return '\n'.join([line.strip() for line in self.root['protocol']])
    else:
      return self.root['protocol']

  def get_target(self):
    """
    Get assay target.

    TODO: Decide which fields are important. We may be able to match
        targets by mol-id.

    Returns
    -------
    target : dict
        A dictionary containing keys for target information types, such
        as 'name', 'mol-id', and 'molecule-type'.
    """
    if 'target' in self.root:
      return self.root['target']
    else:
      return None

  def get_comment(self):
    """
    Get assay comment.
    """
    if "comment" in self.root:
      if isinstance(self.root["comment"], list):
        return "\n".join([line.strip() for line in self.root["comment"]])
      else:
        return self.root["comment"]
    else:
      return None

  def get_results(self):
    """
    Get Assay result fields.
    """
    if "results" in self.root:
      return self.root["results"]
    else:
      return None

  def get_revision(self):
    """
    Get assay revision.
    """
    if "revision" in self.root:
      return self.root["revision"]
    else:
      return None

  def get_data(self):
    """
    Get assay data in a Pandas dataframe.
    """
    try:
      data = self.tree['PC_AssaySubmit']['data']
    except KeyError:
      return None

    # construct a dataframe containing each data point
    columns = []

    # add generic fields from PubChem
    for key in data[0].iterkeys():
      if key == 'data':
        continue
      columns.append(key)

    # add fields specific to this assay
    tids = {}
    for field in self.get_results():
      name = field['name']
      assert name not in columns  # no duplicate field names allowed
      columns.append(name)
      tids[field['tid']] = name
    assert columns is not None

    # populate dataframe
    # note that we use df.append at the end because appending
    # incrementally is much slower
    df = pd.DataFrame(columns=columns)
    series = []
    for dp in data:
      point = {}
      for key, value in dp.iteritems():
        if key == 'data':  # assay-specific fields
          for col in value:
            col_name = tids[col['tid']]
            assert len(col['value']) == 1
            for col_value in col['value'].itervalues():
              point[col_name] = col_value
        else:  # generic fields
          point[key] = value
      series.append(point)
    df = df.append(series)  # does not modify original object
    assert len(df) == len(data)
    assert np.array_equal(df.columns.values, columns)
    return df


class PcbaPandasHandler(object):
    """
    Writes data from PCBA into pandas dataframes.

    Parameters
    ----------
    """
    def __init__(self):
      self.index = 0
      self.df = pd.DataFrame(
          columns=["name", "aid", "activity_outcome_method",
                   "description", "comment", "results", "revision"])
      self.df['aid'] = self.df['aid'].astype(int)  # force AID to int

    def add_dataset(self, filename):
      """
      Adds dataset to internal dataframe.
      """
      parser = PcbaJsonParser(filename)
      row = {}
      row["name"] = parser.get_name()
      row["aid"] = parser.get_aid()
      row["activity_outcome_method"] = parser.get_activity_outcome_method()
      row["description"] = parser.get_description()
      row["comment"] = parser.get_comment()
      row["results"] = parser.get_results()
      row["revision"] = parser.get_revision()
      self.df.loc[self.index] = pd.Series(row)
      self.index += 1  # increment index

    def get_dataset(self, index):
      """
      Fetches information for a particular dataset by index.
      """
      return self.df.loc[index]

    def to_csv(self, out):
      """
      Writes internal dataframe to provided location as csv.
      """
      self.df.to_csv(out)
