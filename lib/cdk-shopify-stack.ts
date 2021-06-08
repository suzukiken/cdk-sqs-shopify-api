import * as cdk from '@aws-cdk/core';
import * as sqs from "@aws-cdk/aws-sqs";
import * as lambda from "@aws-cdk/aws-lambda";
import { SqsEventSource } from "@aws-cdk/aws-lambda-event-sources";
import { PythonFunction } from "@aws-cdk/aws-lambda-python";
import * as secretsmanager from '@aws-cdk/aws-secretsmanager';
import * as dynamodb from '@aws-cdk/aws-dynamodb';

export class CdkShopifyStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    const secret = secretsmanager.Secret.fromSecretNameV2(this, 'Secret', 'shopify/figmentresearchshop1/app/private')
    
    // Dynamodb
    
    const table = new dynamodb.Table(this, "Table", {
      partitionKey: {
        name: "id",
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true
    })
    
    table.addGlobalSecondaryIndex({
      indexName: "batch-epoch-index",
      partitionKey: {
        name: "batch",
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: "epoch",
        type: dynamodb.AttributeType.NUMBER,
      },
    })
    
    // queue

    const queue = new sqs.Queue(this, "Queue", {
      retentionPeriod: cdk.Duration.minutes(10),
      visibilityTimeout: cdk.Duration.seconds(60),
    })
    
    // Lambda

    const lambda_function = new PythonFunction(this, "Function", {
      entry: "lambda",
      index: "shopify_inventory.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_8,
      timeout: cdk.Duration.seconds(60),
      environment: {
        SHOPIFY_PASSWORD: secret.secretValueFromJson('PASSWORD').toString(),
        SHOPIFY_SHOP: secret.secretValueFromJson('SHOP').toString(),
        TABLE_NAME: table.tableName
      },
      //reservedConcurrentExecutions: 1,
    })
    
    lambda_function.addEventSource(
      new SqsEventSource(queue, { batchSize: 1 })
    )
    
    table.grantReadWriteData(lambda_function)
    queue.grantConsumeMessages(lambda_function)
    
    new cdk.CfnOutput(this, "OutputQueue", {
      value: queue.queueName
    })
    
    new cdk.CfnOutput(this, 'OutputTable', { 
      value: table.tableName,
    })
  }
}
