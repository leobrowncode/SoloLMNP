/**
 * Met en forme le Google Sheet « SoloLMNP - Saisie » pour une saisie rapide.
 *
 * Installation (une seule fois) :
 *   1. Ouvrir le Sheet, menu Extensions > Apps Script.
 *   2. Remplacer tout le code par ce fichier, enregistrer.
 *   3. Choisir la fonction « setup » et cliquer Exécuter (autoriser l'accès au tableur).
 *
 * Ensuite la saisie est assistée :
 *   - kind : liste Recette / Dépense ;
 *   - type : liste limitée aux codes de la nature choisie ;
 *   - date : calendrier, format JJ/MM/AAAA ;
 *   - amount : nombre positif, format 1 234,56 € ;
 *   - paid : liste oui / non (non par défaut) ;
 *   - piece_reference : proposée automatiquement (TYPE-AAAA-MM-Tiers), rouge si en double.
 *
 * Les colonnes et l'en-tête ne doivent pas être renommés : SoloLMNP les lit tels quels.
 */

var HEADER = [
  'kind', 'date', 'piece_date', 'type', 'counterparty', 'amount',
  'description', 'piece_reference', 'source_file', 'paid'
];
var KINDS = ['Recette', 'Dépense'];
var REVENUE_TYPES = [
  ['LOY', 'Loyer'],
  ['CHG', 'Charges locataires refacturées'],
  ['TROP', 'Trop-perçu / régularisation'],
  ['AUT', 'Autre recette']
];
var EXPENSE_TYPES = [
  ['ASS', 'Assurance'],
  ['ENT', 'Entretien / réparations'],
  ['FOU', 'Fournitures'],
  ['HON', 'Honoraires'],
  ['BAN', 'Frais bancaires'],
  ['COP', 'Copropriété'],
  ['FON', 'Taxe foncière'],
  ['TAX', 'Autres impôts et taxes'],
  ['GES', 'Gestion locative'],
  ['INT', 'Intérêts (seulement hors échéance de prêt)'],
  ['AUT', 'Autre dépense']
];
var LAST_ROW = 500;
var COL = { kind: 1, date: 2, pieceDate: 3, type: 4, party: 5, amount: 6, desc: 7, ref: 8, file: 9, paid: 10 };

function codes_(list) {
  return list.map(function (item) { return item[0]; });
}

function allTypes_() {
  var seen = {};
  return codes_(REVENUE_TYPES).concat(codes_(EXPENSE_TYPES)).filter(function (code) {
    if (seen[code]) return false;
    seen[code] = true;
    return true;
  });
}

function typeRule_(kind) {
  var list = kind === 'Recette' ? codes_(REVENUE_TYPES)
    : kind === 'Dépense' ? codes_(EXPENSE_TYPES) : allTypes_();
  return SpreadsheetApp.newDataValidation().requireValueInList(list, true).setAllowInvalid(false)
    .setHelpText('Code du type. Voir l\'onglet Aide.').build();
}

function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setSpreadsheetLocale('fr_FR');
  ss.setSpreadsheetTimeZone('Europe/Paris');
  var sheet = ss.getSheets()[0];
  sheet.setName('Saisie');
  sheet.getRange(1, 1, 1, HEADER.length).setValues([HEADER]);
  if (sheet.getMaxRows() < LAST_ROW + 1) sheet.insertRowsAfter(sheet.getMaxRows(), LAST_ROW + 1 - sheet.getMaxRows());
  sheet.setFrozenRows(1);

  var head = sheet.getRange(1, 1, 1, HEADER.length);
  head.setFontWeight('bold').setBackground('#1f6b3a').setFontColor('#ffffff').setHorizontalAlignment('center');
  var widths = [90, 95, 95, 70, 170, 105, 260, 210, 190, 60];
  widths.forEach(function (w, i) { sheet.setColumnWidth(i + 1, w); });

  var rows = LAST_ROW - 1;
  var body = function (col) { return sheet.getRange(2, col, rows, 1); };

  body(COL.kind).setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(KINDS, true).setAllowInvalid(false).build());
  body(COL.type).setDataValidation(typeRule_(''));
  body(COL.paid).setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(['oui', 'non'], true).setAllowInvalid(false).build());

  var dateRule = SpreadsheetApp.newDataValidation().requireDate()
    .setAllowInvalid(false).setHelpText('Date au format JJ/MM/AAAA.').build();
  [COL.date, COL.pieceDate].forEach(function (col) {
    body(col).setNumberFormat('dd/mm/yyyy').setDataValidation(dateRule).setHorizontalAlignment('center');
  });
  body(COL.amount)
    .setNumberFormat('#,##0.00 "€"')
    .setHorizontalAlignment('right')
    .setDataValidation(SpreadsheetApp.newDataValidation().requireNumberGreaterThan(0)
      .setAllowInvalid(false).setHelpText('Montant positif, sans signe.').build());
  body(COL.kind).setHorizontalAlignment('center');
  body(COL.type).setHorizontalAlignment('center');
  body(COL.paid).setHorizontalAlignment('center');

  sheet.getRange(2, 1, rows, HEADER.length).setBorder(null, null, null, null, null, true, '#e4eee4', SpreadsheetApp.BorderStyle.SOLID);
  if (sheet.getFilter()) sheet.getFilter().remove();
  sheet.getRange(1, 1, LAST_ROW, HEADER.length).createFilter();

  var refRange = sheet.getRange(2, COL.ref, rows, 1);
  var rules = [
    // Une même référence ne peut être importée qu'une fois.
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=AND($H2<>"";COUNTIF($H$2:$H$' + LAST_ROW + ';$H2)>1)')
      .setBackground('#f8d7da').setFontColor('#842029').setRanges([refRange]).build(),
    // Dépense en rouge pâle, recette en vert pâle sur la nature.
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2="Recette"')
      .setBackground('#e6f4ea').setRanges([body(COL.kind)]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2="Dépense"')
      .setBackground('#fdf1e3').setRanges([body(COL.kind)]).build(),
    // Ligne incomplète : champs obligatoires vides alors que la ligne est commencée.
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=AND(COUNTA($A2:$G2)>0;OR($A2="";$B2="";$D2="";$E2="";$F2="";$G2=""))')
      .setBackground('#fff3cd').setRanges([sheet.getRange(2, COL.kind, rows, 6), sheet.getRange(2, COL.desc, rows, 1)]).build()
  ];
  sheet.setConditionalFormatRules(rules);

  helpSheet_(ss);
  SpreadsheetApp.getUi().alert(
    'Mise en forme terminée.\n\nSaisissez à partir de la ligne 2. Ensuite copiez les lignes (en-tête compris) ' +
    'et collez-les dans SoloLMNP > Opérations & banque > Transactions.'
  );
}

function helpSheet_(ss) {
  var sheet = ss.getSheetByName('Aide') || ss.insertSheet('Aide');
  sheet.clear();
  var rows = [
    ['Code', 'Nature', 'Libellé'],
  ];
  REVENUE_TYPES.forEach(function (t) { rows.push([t[0], 'Recette', t[1]]); });
  EXPENSE_TYPES.forEach(function (t) { rows.push([t[0], 'Dépense', t[1]]); });
  rows.push(['', '', '']);
  rows.push(['paid', '', 'oui = déjà payé sur le compte bancaire choisi à l\'import ; non = reste à régler.']);
  rows.push(['piece_date', '', 'Date de la facture ou de la quittance. Vide = même date que « date ».']);
  rows.push(['piece_reference', '', 'Unique par pièce. Proposée automatiquement ; deux dépenses du même type, du même mois et du même tiers : ajoutez un suffixe (-2).']);
  rows.push(['Échéances de prêt', '', 'Ne pas saisir ici : SoloLMNP > Opérations & banque > Emprunts > Saisir une échéance.']);
  sheet.getRange(1, 1, rows.length, 3).setValues(rows);
  sheet.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#1f6b3a').setFontColor('#ffffff');
  sheet.setColumnWidth(1, 150); sheet.setColumnWidth(2, 90); sheet.setColumnWidth(3, 620);
  sheet.setFrozenRows(1);
}

function slug_(name) {
  var clean = String(name).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '');
  return clean.slice(0, 24) || 'SANSNOM';
}

/** Déclencheur simple : s'exécute à chaque modification, sans autorisation supplémentaire. */
function onEdit(e) {
  var range = e && e.range;
  if (!range) return;
  var sheet = range.getSheet();
  if (sheet.getName() !== 'Saisie' || range.getRow() < 2 || range.getNumRows() !== 1) return;
  var row = range.getRow();
  var kind = sheet.getRange(row, COL.kind).getValue();

  if (range.getColumn() === COL.kind) {
    var typeCell = sheet.getRange(row, COL.type);
    var current = typeCell.getValue();
    var allowed = kind === 'Recette' ? codes_(REVENUE_TYPES) : kind === 'Dépense' ? codes_(EXPENSE_TYPES) : allTypes_();
    typeCell.setDataValidation(typeRule_(kind));
    if (current && allowed.indexOf(current) === -1) typeCell.clearContent();
  }

  var values = sheet.getRange(row, 1, 1, HEADER.length).getValues()[0];
  var started = values.slice(0, 7).some(function (v) { return v !== ''; });
  if (started && values[COL.paid - 1] === '') sheet.getRange(row, COL.paid).setValue('non');

  var date = values[COL.date - 1];
  var type = values[COL.type - 1];
  var party = values[COL.party - 1];
  if (!values[COL.ref - 1] && date instanceof Date && type && party) {
    var ref = type + '-' + Utilities.formatDate(date, 'Europe/Paris', 'yyyy-MM') + '-' + slug_(party);
    sheet.getRange(row, COL.ref).setValue(ref);
  }
}
