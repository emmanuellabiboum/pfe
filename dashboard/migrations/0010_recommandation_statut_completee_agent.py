from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0009_remove_analysesession_nb_clients_faible_risque_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recommandation",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_attente_validation", "En attente de validation"),
                    ("active", "Active"),
                    ("en_cours", "En cours"),
                    ("completee_agent", "Complétée (à valider)"),
                    ("completee", "Complétée"),
                    ("retiree", "Rejetée"),
                    ("expiree", "Expirée"),
                ],
                default="active",
                max_length=25,
            ),
        ),
    ]

