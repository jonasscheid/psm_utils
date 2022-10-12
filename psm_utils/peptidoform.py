from __future__ import annotations

from typing import Union

from pyteomics import mass, proforma

from psm_utils.exceptions import PSMUtilsException


class Peptidoform:
    """
    Peptide sequence, modifications and charge state represented in ProForma notation.
    """

    def __init__(self, proforma_sequence: str) -> None:
        """
        Peptide sequence, modifications and charge state represented in ProForma notation.

        Parameters
        ----------
        proforma_sequence : str
            Peptidoform sequence in ProForma v2 notation.

        Examples
        --------
        >>> peptidoform = Peptidoform("ACDM[Oxidation]EK")
        >>> peptidoform.theoretical_mass
        711.2567622919099

        Attributes
        ----------
        parsed_sequence : list
            List of tuples with residue and modifications for each location.
        properties : dict[str, Any]
            Dict with sequence-wide properties.

        """
        self.parsed_sequence, self.properties = proforma.parse(proforma_sequence)

        if self.properties["isotopes"]:
            raise NotImplementedError(
                "Peptidoforms with isotopes are currently not supported."
            )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}('{self.proforma}')"

    def __str__(self) -> str:
        return self.proforma

    def __hash__(self) -> int:
        return hash(self.proforma)

    def __eq__(self, __o: object) -> bool:
        try:
            return self.proforma == __o.proforma
        except AttributeError:
            raise NotImplemented("Object is not a Peptidoform")

    @property
    def proforma(self) -> str:
        """Peptidoform sequence in ProForma v2 notation."""
        return proforma.to_proforma(self.parsed_sequence, **self.properties)

    @property
    def sequence(self) -> str:
        """Stripped peptide sequence."""
        return "".join(pos[0] for pos in self.parsed_sequence)

    @property
    def precursor_charge(self) -> int:
        """Syntactic sugar for `Peptidoform.properties['charge_state'].charge`."""
        try:
            return self.properties["charge_state"].charge
        except (AttributeError, KeyError):
            return None

    @property
    def sequential_composition(self) -> list[mass.Composition]:
        """Atomic compositions of both termini and each (modified) residue."""
        # Get compositions for fixed modifications by amino acid
        fixed_rules = {}
        for rule in self.properties["fixed_modifications"]:
            for aa in rule.targets:
                fixed_rules[aa] = rule.modification_tag.composition

        comp_list = []

        # N-terminus
        n_term = mass.Composition({"H": 1})
        if self.properties["n_term"]:
            for tag in self.properties["n_term"]:
                try:
                    n_term += tag.composition
                except (AttributeError, KeyError):
                    raise ModificationException(
                        f"Cannot resolve composition for modification {tag.value}."
                    )
        comp_list.append(n_term)

        # Sequence
        for aa, tags in self.parsed_sequence:
            # Amino acid
            try:
                position_comp = mass.std_aa_comp[aa].copy()
            except (AttributeError, KeyError):
                raise AmbiguousResidueException(
                    f"Cannot resolve composition for amino acid {aa}."
                )
            # Fixed modifications
            if aa in fixed_rules:
                position_comp += fixed_rules[aa]
            # Localized modifications
            if tags:
                for tag in tags:
                    try:
                        position_comp += tag.composition
                    except (AttributeError, KeyError):
                        raise ModificationException(
                            "Cannot resolve composition for modification "
                            f"{tag.value}."
                        )
            comp_list.append(position_comp)

        # C-terminus
        c_term = mass.Composition({"H": 1, "O": 1})
        if self.properties["c_term"]:
            for tag in self.properties["c_term"]:
                try:
                    c_term += tag.composition
                except (AttributeError, KeyError):
                    raise ModificationException(
                        f"Cannot resolve composition for modification {tag.value}."
                    )
        comp_list.append(c_term)

        return comp_list

    @property
    def composition(self) -> mass.Composition:
        """Atomic composition of the full peptidoform."""
        comp = mass.Composition()
        for position_comp in self.sequential_composition:
            comp += position_comp
        for tag in self.properties["labile_modifications"]:
            try:
                comp += tag.composition
            except (AttributeError, KeyError):
                raise ModificationException(
                    f"Cannot resolve composition for modification {tag.value}."
                )
        for tag in self.properties["unlocalized_modifications"]:
            try:
                comp += tag.composition
            except (AttributeError, KeyError):
                raise ModificationException(
                    f"Cannot resolve composition for modification {tag.value}."
                )
        return comp

    @property
    def sequential_theoretical_mass(self) -> float:
        """Monoisotopic mass of both termini and each (modified) residue."""
        fixed_rules = {}
        for rule in self.properties["fixed_modifications"]:
            for aa in rule.targets:
                fixed_rules[aa] = rule.modification_tag.mass

        mass_list = []

        # N-terminus
        n_term = mass.Composition({"H": 1}).mass()
        if self.properties["n_term"]:
            for tag in self.properties["n_term"]:
                try:
                    n_term += tag.mass
                except (AttributeError, KeyError):
                    raise ModificationException(
                        f"Cannot resolve mass for modification {tag.value}."
                    )
        mass_list.append(n_term)

        # Sequence
        for aa, tags in self.parsed_sequence:
            # Amino acid
            try:
                position_mass = mass.std_aa_mass[aa]
            except (AttributeError, KeyError):
                raise AmbiguousResidueException(
                    f"Cannot resolve mass for amino acid {aa}."
                )
            # Fixed modifications
            if aa in fixed_rules:
                position_mass += fixed_rules[aa]
            # Localized modifications
            if tags:
                for tag in tags:
                    try:
                        position_mass += tag.mass
                    except (AttributeError, KeyError):
                        raise ModificationException(
                            "Cannot resolve mass for modification " f"{tag.value}."
                        )
            mass_list.append(position_mass)

        # C-terminus
        c_term = mass.Composition({"H": 1, "O": 1}).mass()
        if self.properties["c_term"]:
            for tag in self.properties["c_term"]:
                try:
                    c_term += tag.mass
                except (AttributeError, KeyError):
                    raise ModificationException(
                        f"Cannot resolve mass for modification {tag.value}."
                    )
        mass_list.append(c_term)

        return mass_list

    @property
    def theoretical_mass(self) -> float:
        """Monoisotopic mass of the full uncharged peptidoform."""
        mass = sum(self.sequential_theoretical_mass)
        for tag in self.properties["labile_modifications"]:
            try:
                mass += tag.mass
            except (AttributeError, KeyError):
                raise ModificationException(
                    f"Cannot resolve mass for modification {tag.value}."
                )
        for tag in self.properties["unlocalized_modifications"]:
            try:
                mass += tag.mass
            except (AttributeError, KeyError):
                raise ModificationException(
                    f"Cannot resolve mass for modification {tag.value}."
                )
        return mass

    @property
    def theoretical_mz(self) -> Union[float, None]:
        """Monoisotopic mz of the full peptidoform."""
        if self.precursor_charge:
            return (
                self.theoretical_mass
                + (mass.nist_mass["H"][1][0] * self.precursor_charge)
            ) / self.precursor_charge
        else:
            return None

    def rename_modifications(self, mapping: dict[str, str]) -> None:
        """
        Apply mapping to rename modification tags.

        Parameters
        ----------
        mapping : dict[str, str]
            Mapping of ``old label`` → ``new label`` for each modification that
            requires renaming. Modification labels that are not in the mapping will not
            be renamed.

        See also
        --------
        psm_utils.psm_list.PSMList.rename_modifications

        Examples
        --------
        >>> peptidoform = Peptidoform('[ac]-PEPTC[cmm]IDEK')
        >>> peptidoform.rename_modifications({
        ...     "ac": "Acetyl",
        ...     "cmm": "Carbamidomethyl"
        ... })
        >>> peptidoform.proforma
        '[Acetyl]-PEPTC[Carbamidomethyl]IDEK'

        """

        def _rename_modification_list(mods):
            new_mods = []
            for mod in mods:
                if mod.value in mapping:
                    new_mods.append(proforma.process_tag_tokens(mapping[mod.value]))
                else:
                    new_mods.append(mod)
            return new_mods

        # Sequential modifications
        for i, (aa, mods) in enumerate(self.parsed_sequence):
            if mods:
                new_mods = _rename_modification_list(mods)
                self.parsed_sequence[i] = (aa, new_mods)

        # Non-sequence modifications
        for mod_type in [
            "n_term",
            "c_term",
            "unlocalized_modifications",
            "labile_modifications",
            "fixed_modifications",
        ]:
            if self.properties[mod_type]:
                self.properties[mod_type] = _rename_modification_list(
                    self.properties[mod_type]
                )

    def add_fixed_modifications(self, modification_rules: list[tuple[str, list[str]]]):
        """
        Add fixed modifications to peptidoform.

        Add modification rules for fixed modifications to peptidoform. These will be
        added in the "fixed modifications" notation, at the front of the ProForma
        sequence.

        See also
        --------
        psm_utils.peptidoform.Peptidoform.add_fixed_modifications

        Examples
        --------
        >>> peptidoform = Peptidoform("ATPEILTCNSIGCLK")
        >>> peptidoform.add_fixed_modifications([("Carbamidomethyl", ["C"])])
        >>> peptidoform.proforma
        '<[Carbamidomethyl]@C>ATPEILTCNSIGCLK'

        """
        modification_rules = [
            proforma.ModificationRule(proforma.process_tag_tokens(mod), targets)
            for mod, targets in modification_rules
        ]
        if self.properties["fixed_modifications"]:
            self.properties["fixed_modifications"].extend(modification_rules)
        else:
            self.properties["fixed_modifications"] = modification_rules

    def apply_fixed_modifications(self):
        """
        Apply ProForma fixed modifications as sequential modifications.

        Applies all modifications that are encoded as fixed in the ProForma notation
        (once at the beginning of the sequence) as modifications throughout the
        sequence at each affected amino acid residue.

        See also
        --------
        psm_utils.peptidoform.Peptidoform.apply_fixed_modifications

        Examples
        --------
        >>> peptidoform = Peptidoform('<[Carbamidomethyl]@C>ATPEILTCNSIGCLK')
        >>> peptidoform.apply_fixed_modifications()
        >>> peptidoform.proforma
        'ATPEILTC[Carbamidomethyl]NSIGC[Carbamidomethyl]LK'

        """
        if self.properties["fixed_modifications"]:
            # Setup target_aa -> modification_list dictionary
            rule_dict = {}
            for rule in self.properties["fixed_modifications"]:
                for target_aa in rule.targets:
                    try:
                        rule_dict[target_aa].append(rule.modification_tag)
                    except KeyError:
                        rule_dict[target_aa] = [rule.modification_tag]

            # Apply modifications to sequence
            for i, (aa, site_mods) in enumerate(self.parsed_sequence):
                if aa in rule_dict:
                    if site_mods:
                        self.parsed_sequence[i] = (aa, site_mods + rule_dict[aa])
                    else:
                        self.parsed_sequence[i] = (aa, rule_dict[aa])

            # Remove fixed modifications
            self.properties["fixed_modifications"] = None


class PeptidoformException(PSMUtilsException):
    """Error while handling :py:class:`Peptidoform`."""

    pass


class AmbiguousResidueException(PeptidoformException):
    """Error while handling ambiguous residue."""

    pass


class ModificationException(PeptidoformException):
    """Error while handling amino acid modification."""

    pass
