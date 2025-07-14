gcloud run deploy rent-api \
    --image asia-east1-docker.pkg.dev/adept-turbine-339912/rent-api-repo/rent-api \
    --platform managed \
    --region asia-east1 \
    --allow-unauthenticated \
    --set-env-vars "PROJECT_ID=adept-turbine-339912,DATASET_ID=Cathay_Bank_Demo,TABLE_ID=591_rentdata"