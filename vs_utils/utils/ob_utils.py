"""
Open Babel utilities.
"""

__author__ = "Steven Kearnes"
__copyright__ = "Copyright 2014, Stanford University"
__license__ = "BSD 3-clause"

from StringIO import StringIO
import subprocess

from rdkit import Chem
from rdkit_utils import serial

from vs_utils.utils import image_utils


class Ionizer(object):
    """
    Calculate atomic formal charges at the given pH.

    Parameters
    ----------
    pH : float, optional (default 7.4)
        pH at which to calculate formal charges.
    """
    def __init__(self, pH=7.4):
        self.pH = pH

    def __call__(self, mol):
        """
        Ionize a molecule.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        """
        return self.ionize(mol)

    def ionize(self, mol):
        """
        Ionize a molecule while preserving 3D coordinates.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        """
        if mol.GetNumConformers() > 0:
            return self._ionize_3d(mol)
        else:
            return self._ionize_2d(mol)

    def _ionize_2d(self, mol):
        """
        Ionize a molecule without preserving conformers.

        Note: this method removes explicit hydrogens from the molecule.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        """
        smiles = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)
        args = ['obabel', '-i', 'can', '-o', 'can', '-p', str(self.pH)]
        p = subprocess.Popen(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        ionized_smiles, _ = p.communicate(smiles)
        ionized_mol = Chem.MolFromSmiles(ionized_smiles)

        # catch ionizer error
        if ionized_mol is None:
            raise IonizerError(mol)

        return ionized_mol

    def _ionize_3d(self, mol):
        """
        Ionize a molecule while preserving conformers.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        """
        assert mol.GetNumConformers() > 0
        sdf = ''
        for conf in mol.GetConformers():
            sdf += Chem.MolToMolBlock(mol, confId=conf.GetId(),
                                      includeStereo=True)
            sdf += '$$$$\n'
        args = ['obabel', '-i', 'sdf', '-o', 'sdf', '-p', str(self.pH)]
        p = subprocess.Popen(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        ionized_sdf, _ = p.communicate(sdf)
        reader = serial.MolReader(StringIO(ionized_sdf), mol_format='sdf',
                                  remove_salts=False)  # no changes
        try:
            mols = list(reader.get_mols())
        except RuntimeError as e:  # catch pre-condition violations
            raise IonizerError(e.message)

        # catch ionizer failure
        if len(mols) == 0:
            raise IonizerError(mol)

        # detection of stereochemistry based on 3D coordinates might result
        # in issues when attempting to recombine ionized conformers, but we
        # merge them anyway
        if len(mols) == 1:
            ionized_mol, = mols
        else:
            ionized_mol = mols[0]
            for other in mols[1:]:
                for conf in other.GetConformers():
                    ionized_mol.AddConformer(conf, assignId=True)
        return ionized_mol


class MolImage(object):
    """
    Generate 2D depictions of molecules.

    Parameters
    ----------
    size : int, optional (default 32)
        Size (in any direction) of generated images.
    """
    def __init__(self, size=32):
        self.size = size

    def __call__(self, mol):
        """
        Generate a PNG image from a SMILES string.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        size : int, optional (default 32)
            Size (in any direction) of generated image.
        """
        return self.depict(mol)

    def depict(self, mol):
        """
        Generate a PNG image from a SMILES string.

        Parameters
        ----------
        mol : RDMol
            Molecule.
        size : int, optional (default 32)
            Size (in any direction) of generated image.
        """
        smiles = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)
        args = ['obabel', '-i', 'can', '-o', 'png', '-xd', '-xC',
                '-xp {}'.format(self.size)]
        p = subprocess.Popen(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        png, _ = p.communicate(smiles)
        im = image_utils.load(png)
        return im


class IonizerError(Exception):
    """
    Generic Ionizer exception.
    """
